from mcp.server.fastmcp import FastMCP
from patient_data import (
    fetch_patient_summary, 
    detect_anomalous_glucose_events,
    find_last_hypoglycemic_event,
    analyze_glucose_patterns
)
from flask import Flask, request, jsonify
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import threading
import os
import sys
import socket
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from db_config import db_config
from models import Glucose, Sleep, Exercise, Base

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger(__name__)

class HighFrequencyCGMReceiver:
    """
    Optimized receiver for high-frequency CGM data (5-minute intervals)
    Uses Amazon RDS MySQL for storage
    """
    
    def __init__(self):
        self.db_config = db_config
        self.init_database()
    
    def init_database(self):
        """Verify database tables exist (tables are already created in RDS)"""
        try:
            # Tables already exist in RDS, just verify connection
            # SQLAlchemy will use existing tables
            from sqlalchemy import inspect
            inspector = inspect(self.db_config.engine)
            existing_tables = inspector.get_table_names()
            logger.info(f"✅ Connected to RDS. Existing tables: {', '.join(existing_tables)}")
            logger.info(f"✅ Using tables: blood_glucose, sleep_data, exercise_data on {self.db_config.host}")
        except Exception as e:
            logger.error(f"❌ Error verifying database: {e}")
            raise
    
    def process_cgm_data(self, data: Dict, patient_id: str = None, session_id: str = None, automation_type: str = None) -> Dict:
        """
        Process high-frequency CGM data from Health Auto Export using SQLAlchemy
        """
        session = None
        try:
            if not patient_id:
                patient_id = "cgm_patient"
            
            session = self.db_config.get_session()
            
            processed_glucose = 0
            processed_sleep = 0
            processed_exercise = 0
            processed_other = 0
            
            logger.info(f"Processing CGM data - Session: {session_id}, Type: {automation_type}")
            
            # Handle different data formats
            if isinstance(data, list):
                metrics_list = data
            elif "data" in data:
                metrics_list = data["data"] if isinstance(data["data"], list) else data["data"].get("metrics", [])
            elif "metrics" in data:
                metrics_list = data["metrics"]
            else:
                metrics_list = data if isinstance(data, list) else []
            
            for item in metrics_list:
                try:
                    if not isinstance(item, dict):
                        continue
                    
                    metric_name = item.get("name", item.get("type", item.get("metric", "unknown")))
                    value = item.get("qty", item.get("value", item.get("amount", 0)))
                    unit = item.get("units", item.get("unit", ""))
                    timestamp = item.get("date", item.get("timestamp", item.get("startDate", datetime.now().isoformat())))
                    source_name = item.get("source", item.get("sourceName", "Health Auto Export"))
                    
                    # Skip non-numeric values
                    if not isinstance(value, (int, float)):
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            continue
                    
                    # Parse timestamp
                    try:
                        clean_timestamp = timestamp.replace('Z', '').replace('+00:00', '')
                        if 'T' in clean_timestamp:
                            dt = datetime.fromisoformat(clean_timestamp)
                        else:
                            dt = datetime.strptime(clean_timestamp, '%Y-%m-%d %H:%M:%S')
                        
                        date_str = dt.strftime('%Y-%m-%d')
                        hour = dt.hour
                        minute = dt.minute
                    except Exception as e:
                        logger.warning(f"Error parsing timestamp {timestamp}: {e}")
                        dt = datetime.now()
                        date_str = dt.strftime('%Y-%m-%d')
                        hour = dt.hour
                        minute = dt.minute
                    
                    # Route data to appropriate table: glucose, sleep, or exercise
                    is_glucose = any(term in metric_name.lower() for term in ['glucose', 'blood', 'bg'])
                    is_sleep = any(term in metric_name.lower() for term in ['sleep', 'rest'])
                    is_exercise = any(term in metric_name.lower() for term in ['workout', 'exercise', 'activity', 'fitness'])
                    
                    # Check for sleep data (has start and end times)
                    if 'startDate' in item and 'endDate' in item:
                        try:
                            sleep_start = datetime.fromisoformat(item['startDate'].replace('Z', '').replace('+00:00', ''))
                            sleep_end = datetime.fromisoformat(item['endDate'].replace('Z', '').replace('+00:00', ''))
                            duration_minutes = int((sleep_end - sleep_start).total_seconds() / 60)
                            
                            # Insert sleep data into sleep_data table
                            sleep_record = Sleep(
                                date=sleep_start.date(),
                                bedtime=sleep_start,
                                wake_time=sleep_end,
                                sleep_duration_minutes=duration_minutes,
                                deep_sleep_minutes=item.get('deepSleepMinutes', None),
                                light_sleep_minutes=item.get('lightSleepMinutes', None),
                                rem_sleep_minutes=item.get('remSleepMinutes', None),
                                sleep_efficiency=item.get('sleepEfficiency', None),
                                heart_rate_avg=item.get('heartRateAvg', None),
                                heart_rate_min=item.get('heartRateMin', None),
                                heart_rate_max=item.get('heartRateMax', None)
                            )
                            session.merge(sleep_record)
                            processed_sleep += 1
                        except IntegrityError:
                            # Duplicate entry, skip
                            session.rollback()
                            continue
                        except Exception as e:
                            logger.warning(f"Error processing sleep data: {e}")
                            continue
                    
                    # Check for exercise/workout data
                    if is_exercise or 'workoutActivityType' in item:
                        try:
                            exercise_start = dt
                            exercise_end_str = item.get('endDate')
                            if exercise_end_str:
                                if isinstance(exercise_end_str, str):
                                    exercise_end = datetime.fromisoformat(exercise_end_str.replace('Z', '').replace('+00:00', ''))
                                else:
                                    exercise_end = exercise_end_str
                            else:
                                exercise_end = exercise_start + timedelta(minutes=30)
                            
                            duration_mins = item.get('duration', 0)
                            if isinstance(duration_mins, str):
                                try:
                                    duration_mins = float(duration_mins)
                                except:
                                    duration_mins = (exercise_end - exercise_start).total_seconds() / 60
                            
                            # Insert exercise data into exercise_data table
                            exercise_record = Exercise(
                                timestamp=exercise_start,
                                activity_type=item.get('workoutActivityType', metric_name),
                                duration_minutes=int(duration_mins) if duration_mins else None,
                                calories_burned=item.get('totalEnergyBurned', 0),
                                distance_km=item.get('totalDistance', 0),
                                steps=item.get('steps', None),
                                active_energy_kcal=item.get('totalEnergyBurned', 0),
                                resting_energy_kcal=None
                            )
                            session.merge(exercise_record)
                            processed_exercise += 1
                        except IntegrityError:
                            # Duplicate entry, skip
                            session.rollback()
                            continue
                        except Exception as e:
                            logger.warning(f"Error processing exercise data: {e}")
                            continue
                    
                    # Store glucose data
                    if is_glucose or automation_type == "cgm-frequent":
                        try:
                            # Insert glucose data into blood_glucose table
                            glucose_record = Glucose(
                                timestamp=dt,
                                value=value,
                                unit='mg/dL',
                                source=source_name or 'cgm'
                            )
                            session.merge(glucose_record)
                            processed_glucose += 1
                        except IntegrityError:
                            # Duplicate entry, skip
                            session.rollback()
                            continue
                        except Exception as e:
                            logger.warning(f"Database error inserting glucose reading: {e}")
                            continue
                        
                except Exception as e:
                    logger.warning(f"Error processing individual metric: {e}")
                    continue
            
            session.commit()
            
            result = {
                "status": "success",
                "processed_glucose": processed_glucose,
                "processed_sleep": processed_sleep,
                "processed_exercise": processed_exercise,
                "processed_other": processed_other,
                "patient_id": patient_id,
                "session_id": session_id,
                "automation_type": automation_type,
                "timestamp": datetime.now().isoformat()
            }
            
            if processed_glucose > 0:
                logger.info(f"✅ Stored {processed_glucose} glucose readings")
            if processed_sleep > 0:
                logger.info(f"✅ Stored {processed_sleep} sleep records")
            if processed_exercise > 0:
                logger.info(f"✅ Stored {processed_exercise} exercise records")
            if processed_other > 0:
                logger.info(f"✅ Stored {processed_other} other records")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing CGM data: {e}")
            if session:
                session.rollback()
            return {"status": "error", "message": str(e), "patient_id": patient_id}
        finally:
            if session:
                session.close()
    
    def get_recent_cgm_readings(self, patient_id: str = None, minutes_back: int = 60) -> List[Dict]:
        """Get recent glucose readings using SQLAlchemy (blood_glucose table)"""
        session = None
        try:
            session = self.db_config.get_session()
        
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=minutes_back)
        
            
            results = session.query(Glucose).filter(
                Glucose.timestamp >= start_time
            ).order_by(Glucose.timestamp.desc()).limit(100).all()
            
            readings = []
            for record in results:
                timestamp_dt = record.timestamp
                readings.append({
                    "timestamp": timestamp_dt.isoformat() if timestamp_dt else None,
                    "glucose_mg_dl": float(record.value) if record.value is not None else None,
                    "source": record.source,
                    "unit": record.unit,
                    "minutes_ago": round((end_time - timestamp_dt).total_seconds() / 60, 1) if timestamp_dt else None
                })
            
            return readings
        except Exception as e:
            logger.error(f"Error getting recent CGM readings: {e}")
            return []
        finally:
            if session:
                session.close()
    
    def get_cgm_stats(self, patient_id: str = None, hours_back: int = 24) -> Dict:
        """Get CGM statistics for the specified time period using SQLAlchemy"""
        session = None
        try:
            session = self.db_config.get_session()
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
            from sqlalchemy import func
            
            result = session.query(
                func.count(Glucose.id).label('count'),
                func.avg(Glucose.value).label('avg_glucose'),
                func.min(Glucose.value).label('min_glucose'),
                func.max(Glucose.value).label('max_glucose'),
                func.min(Glucose.timestamp).label('first_reading'),
                func.max(Glucose.timestamp).label('last_reading')
            ).filter(
                Glucose.timestamp >= start_time
            ).first()
            
            if result and result.count > 0:
                count = result.count
                avg_glucose = float(result.avg_glucose) if result.avg_glucose else 0
                min_glucose = float(result.min_glucose) if result.min_glucose else 0
                max_glucose = float(result.max_glucose) if result.max_glucose else 0
                first_reading = result.first_reading
                last_reading = result.last_reading
            
            # Calculate expected vs actual readings (12 per hour for 5-min frequency)
            expected_readings = hours_back * 12
            data_completeness = (count / expected_readings) * 100 if expected_readings > 0 else 0
            
            return {
                "total_readings": count,
                "expected_readings": expected_readings,
                "data_completeness_percent": round(data_completeness, 1),
                "average_glucose": round(avg_glucose, 1),
                "min_glucose": round(min_glucose, 1),
                "max_glucose": round(max_glucose, 1),
                "glucose_range": round(max_glucose - min_glucose, 1),
                    "first_reading_time": first_reading.isoformat() if first_reading else None,
                    "last_reading_time": last_reading.isoformat() if last_reading else None,
                "time_range_hours": hours_back
            }
        else:
            return {
                "total_readings": 0,
                "message": "No CGM data found in specified time range"
            }
        except Exception as e:
            logger.error(f"Error getting CGM stats: {e}")
            return {
                "total_readings": 0,
                "message": f"Error retrieving stats: {str(e)}"
            }
        finally:
            if session:
                session.close()
    
    def get_glucose_data(self, patient_id: str = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> List[Dict]:
        """Get glucose data from RDS using SQLAlchemy (blood_glucose table)"""
        session = None
        try:
            session = self.db_config.get_session()
            
            query = session.query(Glucose)  # No patient_id filter - table doesn't have it
            
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include end date
                query = query.filter(Glucose.timestamp >= start_dt, Glucose.timestamp < end_dt)
            
            results = query.order_by(Glucose.timestamp.desc()).limit(limit).all()
            
            return [record.to_dict() for record in results]
        except Exception as e:
            logger.error(f"Error getting glucose data: {e}")
            return []
        finally:
            if session:
                session.close()
    
    def get_sleep_data(self, patient_id: str = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> List[Dict]:
        """Get sleep data from RDS using SQLAlchemy (sleep_data table)"""
        session = None
        try:
            session = self.db_config.get_session()
            
            query = session.query(Sleep)  # No patient_id filter - table doesn't have it
            
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Sleep.date >= start_dt, Sleep.date <= end_dt)
            
            results = query.order_by(Sleep.bedtime.desc()).limit(limit).all()
            
            return [record.to_dict() for record in results]
        except Exception as e:
            logger.error(f"Error getting sleep data: {e}")
            return []
        finally:
            if session:
                session.close()
    
    def get_exercise_data(self, patient_id: str = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> List[Dict]:
        """Get exercise data from RDS using SQLAlchemy (exercise_data table)"""
        session = None
        try:
            session = self.db_config.get_session()
            
            query = session.query(Exercise)  # No patient_id filter - table doesn't have it
            
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include end date
                query = query.filter(Exercise.timestamp >= start_dt, Exercise.timestamp < end_dt)
            
            results = query.order_by(Exercise.timestamp.desc()).limit(limit).all()
            
            return [record.to_dict() for record in results]
        except Exception as e:
            logger.error(f"Error getting exercise data: {e}")
            return []
        finally:
            if session:
                session.close()

# Initialize CGM receiver (lazy initialization to avoid blocking MCP startup)
_cgm_receiver = None

def get_cgm_receiver():
    """Get or create CGM receiver instance (lazy initialization)"""
    global _cgm_receiver
    if _cgm_receiver is None:
        _cgm_receiver = HighFrequencyCGMReceiver()
    return _cgm_receiver

# Flask server for receiving data
app = Flask(__name__)

@app.route('/health-data', methods=['POST'])
def receive_health_data():
    """Endpoint optimized for high-frequency CGM data"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Get automation info from headers
        session_id = request.headers.get('session-id', request.headers.get('Session-Id', 'unknown'))
        automation_type = request.headers.get('automation-type', request.headers.get('Automation-Type', 'unknown'))
        automation_name = request.headers.get('automation-name', request.headers.get('Automation-Name', 'unknown'))
        
        # Log incoming request
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"[{current_time}] 📡 Received data - Type: {automation_type}, Session: {session_id[:8]}...")
        
        # Process the data
        result = get_cgm_receiver().process_cgm_data(
            data=data,
            patient_id="cgm_patient",
            session_id=session_id,
            automation_type=automation_type
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"❌ Error receiving health data: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e), 
            "timestamp": datetime.now().isoformat()
        }), 400

@app.route('/cgm-status', methods=['GET'])
def cgm_status():
    """Get current CGM monitoring status"""
    try:
        stats_1h = get_cgm_receiver().get_cgm_stats(hours_back=1)
        stats_24h = get_cgm_receiver().get_cgm_stats(hours_back=24)
        recent_readings = get_cgm_receiver().get_recent_cgm_readings(minutes_back=30)
        
        return jsonify({
            "status": "healthy",
            "service": "5-Minute CGM Monitor",
            "timestamp": datetime.now().isoformat(),
            "last_hour": stats_1h,
            "last_24_hours": stats_24h,
            "recent_readings": len(recent_readings),
            "latest_reading": recent_readings[0] if recent_readings else None
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def get_server_url():
    """Get the server URL with local IP address"""
    try:
        # Get local IP address
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Alternative method if above doesn't work
        if local_ip.startswith('127.'):
            import subprocess
            try:
                # For macOS/Linux
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                if result.returncode == 0:
                    local_ip = result.stdout.strip().split()[0]
            except:
                # Fallback method
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.connect(('8.8.8.8', 80))
                    local_ip = s.getsockname()[0]
                except:
                    local_ip = '192.168.1.XXX'
                finally:
                    s.close()
        
        return local_ip
    except:
        return '192.168.1.XXX'

def run_flask_server(port: int = 5000):
    """Run Flask server for CGM data reception - output suppressed to avoid breaking MCP"""
    try:
    logger.info(f"🏥 Starting 5-Minute CGM Flask server on port {port}")
        
        # Completely suppress Flask's stdout output to avoid breaking MCP protocol
        import sys
        import logging
        import werkzeug.serving
        import os
        
        # Suppress werkzeug (Flask's WSGI server) output completely
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.disabled = True
        
        # Suppress Flask CLI output
        cli_logger = logging.getLogger('flask.cli')
        cli_logger.disabled = True
        
        # Redirect stdout to stderr for Flask's output
        original_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        try:
            # Run Flask - all output goes to stderr now
            app.run(
                host='0.0.0.0', 
                port=port, 
                debug=False, 
                use_reloader=False, 
                threaded=True
            )
        finally:
            # Restore stdout (though we won't reach here in daemon thread)
            sys.stdout = original_stdout
            
    except Exception as e:
        logger.error(f"❌ Flask server error: {e}")
        # Don't raise - allow MCP server to continue even if Flask fails
        pass

# Initialize MCP server
mcp = FastMCP(name="HighFrequencyCGMMonitoring")

# Enhanced MCP tools for 5-minute CGM monitoring
@mcp.tool()
def get_live_cgm_data(minutes_back: int = 30) -> dict:
    """
    Get live CGM readings from the last X minutes.
    
    Args:
        minutes_back (int): Number of minutes of CGM data to retrieve (default: 30)
    """
    try:
        readings = get_cgm_receiver().get_recent_cgm_readings(minutes_back=minutes_back)
        
        if not readings:
            return {
                "data_source": "5-Minute CGM Monitor",
                "message": "No CGM data found. Check Health Auto Export app configuration.",
                "minutes_analyzed": minutes_back,
                "total_readings": 0,
                "setup_check": "Visit http://localhost:5000/cgm-status for system status"
            }
        
        # Calculate glucose statistics
        glucose_values = [r["glucose_mg_dl"] for r in readings if r["glucose_mg_dl"]]
        
        # Expected readings (every 5 minutes)
        expected_readings = minutes_back // 5
        data_completeness = (len(readings) / expected_readings) * 100 if expected_readings > 0 else 0
        
        return {
            "data_source": "5-Minute CGM Monitor",
            "minutes_analyzed": minutes_back,
            "total_readings": len(readings),
            "expected_readings": expected_readings,
            "data_completeness_percent": round(data_completeness, 1),
            "latest_reading": readings[0] if readings else None,
            "glucose_stats": {
                "current_glucose": readings[0]["glucose_mg_dl"] if readings else None,
                "average_glucose": round(sum(glucose_values) / len(glucose_values), 1) if glucose_values else None,
                "min_glucose": min(glucose_values) if glucose_values else None,
                "max_glucose": max(glucose_values) if glucose_values else None,
                "glucose_trend": "stable"  # Could add trend calculation
            },
            "readings": readings[:20]  # Show last 20 readings
        }
        
    except Exception as e:
        logger.error(f"Error getting live CGM data: {e}")
        return {"error": str(e), "data_source": "5-Minute CGM Monitor"}

@mcp.tool()
def get_cgm_monitoring_status() -> dict:
    """
    Check the status of 5-minute CGM monitoring system.
    """
    try:
        # Get system stats
        stats_1h = get_cgm_receiver().get_cgm_stats(hours_back=1)
        stats_24h = get_cgm_receiver().get_cgm_stats(hours_back=24)
        recent_readings = get_cgm_receiver().get_recent_cgm_readings(minutes_back=15)
        
        # Get server URL
        server_ip = get_server_url()
        
        return {
            "system_status": "running",
            "cgm_frequency": "Every 5 minutes",
            "server_endpoint": f"http://{server_ip}:5000/health-data",
            "status_page": f"http://{server_ip}:5000/cgm-status",
            "last_hour_performance": stats_1h,
            "last_24h_performance": stats_24h,
            "recent_activity": {
                "readings_last_15_min": len(recent_readings),
                "latest_reading": recent_readings[0] if recent_readings else None,
                "system_responsive": len(recent_readings) > 0
            },
            "health_auto_export_setup": {
                "app_url": f"http://{server_ip}:5000/health-data",
                "frequency_setting": "Quantity: 5, Interval: minutes",
                "data_type": "Health Metrics (Blood Glucose only)",
                "format": "JSON",
                "headers": "automation-type: cgm-frequent"
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking CGM monitoring status: {e}")
        return {"error": str(e), "system_status": "error"}

@mcp.tool()
def start_cgm_server(port: int = 5000) -> dict:
    """
    Start the 5-minute CGM monitoring server.
    
    Args:
        port (int): Port number for the server (default: 5000)
    """
    try:
        # Start Flask server in background
        flask_thread = threading.Thread(target=run_flask_server, args=(port,), daemon=True)
        flask_thread.start()
        
        server_ip = get_server_url()
        
        return {
            "status": "started",
            "message": "5-Minute CGM monitoring server started successfully",
            "server_details": {
                "endpoint": f"http://{server_ip}:{port}/health-data",
                "status_page": f"http://{server_ip}:{port}/cgm-status",
                "local_access": f"http://localhost:{port}/cgm-status"
            },
            "health_auto_export_configuration": {
                "url_to_enter": f"http://{server_ip}:{port}/health-data",
                "quantity": 5,
                "interval": "minutes",
                "data_type": "Health Metrics",
                "select_metrics": "Blood Glucose only",
                "format": "JSON",
                "headers_to_add": {
                    "automation-type": "cgm-frequent",
                    "Content-Type": "application/json"
                }
            },
            "next_steps": [
                "1. Open Health Auto Export app on iPhone",
                "2. Create or edit automation",
                f"3. Set URL to: http://{server_ip}:{port}/health-data",
                "4. Set Quantity: 5, Interval: minutes",
                "5. Select only Blood Glucose data",
                "6. Test with Manual Export",
                "7. Monitor data at status page"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error starting CGM server: {e}")
        return {"error": str(e)}

@mcp.tool()
def get_glucose_data(patient_id: str = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> dict:
    """
    Get glucose data from RDS MySQL database.
    
    Args:
        patient_id (str): Patient identifier (default: "cgm_patient")
        start_date (str): Start date in YYYY-MM-DD format (optional)
        end_date (str): End date in YYYY-MM-DD format (optional)
        limit (int): Maximum number of records to return (default: 1000)
    """
    try:
        data = get_cgm_receiver().get_glucose_data(patient_id, start_date, end_date, limit)
        return {
            "table": "glucose",
            "patient_id": patient_id,
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting glucose data: {e}")
        return {"error": str(e), "table": "glucose"}

@mcp.tool()
def get_sleep_data(patient_id: str = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> dict:
    """
    Get sleep data from RDS MySQL database.
    
    Args:
        patient_id (str): Patient identifier (default: "cgm_patient")
        start_date (str): Start date in YYYY-MM-DD format (optional)
        end_date (str): End date in YYYY-MM-DD format (optional)
        limit (int): Maximum number of records to return (default: 1000)
    """
    try:
        data = get_cgm_receiver().get_sleep_data(patient_id, start_date, end_date, limit)
        return {
            "table": "sleep",
            "patient_id": patient_id,
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting sleep data: {e}")
        return {"error": str(e), "table": "sleep"}

@mcp.tool()
def get_exercise_data(patient_id: str = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> dict:
    """
    Get exercise/workout data from RDS MySQL database.
    
    Args:
        patient_id (str): Patient identifier (default: "cgm_patient")
        start_date (str): Start date in YYYY-MM-DD format (optional)
        end_date (str): End date in YYYY-MM-DD format (optional)
        limit (int): Maximum number of records to return (default: 1000)
    """
    try:
        data = get_cgm_receiver().get_exercise_data(patient_id, start_date, end_date, limit)
        return {
            "table": "exercise",
            "patient_id": patient_id,
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting exercise data: {e}")
        return {"error": str(e), "table": "exercise"}

if __name__ == "__main__":
    # When running as MCP server, all output must go to stderr, not stdout
    # MCP communicates via JSON on stdout, so any print() will break it
    logger.info("🩸 Starting 5-Minute CGM Monitoring System...")
    logger.info("=" * 50)
    
    # Try to start Flask server on port 5000, fallback to 5001 if busy
    # Note: Flask server is optional - MCP tools work without it
    try:
        import socket
        flask_port = 5000
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 5000))
        sock.close()
        if result == 0:
            logger.warning(f"⚠️  Port 5000 is in use, trying port 5001...")
            flask_port = 5001
        
        # Start Flask server in background (non-blocking)
        flask_thread = threading.Thread(target=run_flask_server, args=(flask_port,), daemon=True)
    flask_thread.start()
        
        # Give Flask a moment to start
        import time
        time.sleep(0.5)
    
    # Get and display server information
    server_ip = get_server_url()
    
        logger.info(f"✅ CGM Server Started Successfully!")
        logger.info(f"📡 Data Endpoint: http://{server_ip}:{flask_port}/health-data")
        logger.info(f"📊 Status Page: http://{server_ip}:{flask_port}/cgm-status") 
        logger.info(f"🔗 Local Status: http://localhost:{flask_port}/cgm-status")
        logger.info("=" * 50)
        logger.info("📱 Health Auto Export Configuration:")
        logger.info(f"   URL: http://{server_ip}:{flask_port}/health-data")
        logger.info(f"   Frequency: Quantity=5, Interval=minutes")
        logger.info(f"   Data: Blood Glucose only")
        logger.info(f"   Format: JSON")
        logger.info("=" * 50)
    except Exception as e:
        logger.warning(f"⚠️  Could not start Flask server: {e}")
        logger.info("ℹ️  MCP tools will still work without Flask server")
    
    logger.info("🚀 Starting MCP server...")
    
    # Start MCP server
    mcp.run(transport='stdio')