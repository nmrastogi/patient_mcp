from mcp.server.fastmcp import FastMCP
from patient_data import (
    fetch_patient_summary, 
    detect_anomalous_glucose_events,
    find_last_hypoglycemic_event,
    analyze_glucose_patterns
)
from flask import Flask, request, jsonify
import json
import pymysql
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import threading
import os
import sys
import socket
from db_config import db_config

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
        """Initialize MySQL database optimized for high-frequency CGM data"""
        conn = None
        try:
            conn = self.db_config.get_connection()
            cursor = conn.cursor()
            
            # Optimized table for frequent glucose readings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cgm_readings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    patient_id VARCHAR(255),
                    glucose_mg_dl DOUBLE,
                    timestamp DATETIME,
                    date DATE,
                    hour INT,
                    minute INT,
                    source_name VARCHAR(255),
                    automation_type VARCHAR(255),
                    session_id VARCHAR(255),
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_patient_timestamp (patient_id, timestamp),
                    INDEX idx_cgm_timestamp (patient_id, timestamp DESC),
                    INDEX idx_cgm_date_hour (patient_id, date, hour)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            # Table for other health metrics (hourly)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    patient_id VARCHAR(255),
                    metric_name VARCHAR(255),
                    value DOUBLE,
                    unit VARCHAR(50),
                    timestamp DATETIME,
                    date DATE,
                    source_name VARCHAR(255),
                    automation_type VARCHAR(255),
                    session_id VARCHAR(255),
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_patient_metric_timestamp (patient_id, metric_name, timestamp),
                    INDEX idx_health_timestamp (patient_id, timestamp DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            # Table for workouts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workouts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    patient_id VARCHAR(255),
                    workout_type VARCHAR(255),
                    duration_minutes DOUBLE,
                    total_distance DOUBLE,
                    distance_unit VARCHAR(50),
                    total_energy DOUBLE,
                    energy_unit VARCHAR(50),
                    start_time DATETIME,
                    end_time DATETIME,
                    source_name VARCHAR(255),
                    automation_type VARCHAR(255),
                    session_id VARCHAR(255),
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_patient_workout_start (patient_id, workout_type, start_time),
                    INDEX idx_workout_timestamp (patient_id, start_time DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            conn.commit()
            logger.info(f"✅ High-frequency CGM MySQL database initialized on {self.db_config.host}")
            
        except Exception as e:
            logger.error(f"❌ Error initializing database: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def process_cgm_data(self, data: Dict, patient_id: str = None, session_id: str = None, automation_type: str = None) -> Dict:
        """
        Process high-frequency CGM data from Health Auto Export
        """
        conn = None
        try:
            if not patient_id:
                patient_id = "cgm_patient"
            
            conn = self.db_config.get_connection()
            cursor = conn.cursor()
            
            processed_glucose = 0
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
                        # MySQL uses DATETIME format
                        mysql_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                        hour = dt.hour
                        minute = dt.minute
                    except Exception as e:
                        logger.warning(f"Error parsing timestamp {timestamp}: {e}")
                        dt = datetime.now()
                        date_str = dt.strftime('%Y-%m-%d')
                        mysql_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                        hour = dt.hour
                        minute = dt.minute
                    
                    # Check if this is glucose data
                    is_glucose = any(term in metric_name.lower() for term in ['glucose', 'blood', 'bg'])
                    
                    if is_glucose or automation_type == "cgm-frequent":
                        # Store in CGM table for fast access
                        try:
                            cursor.execute('''
                                INSERT IGNORE INTO cgm_readings 
                                (patient_id, glucose_mg_dl, timestamp, date, hour, minute, 
                                 source_name, automation_type, session_id, raw_data)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''', (patient_id, value, mysql_timestamp, date_str, hour, minute,
                                  source_name, automation_type, session_id, json.dumps(item)))
                            
                            processed_glucose += 1
                            
                        except pymysql.Error as e:
                            logger.warning(f"Database error inserting CGM reading: {e}")
                            continue
                    else:
                        # Store other metrics in general table
                        try:
                            cursor.execute('''
                                INSERT IGNORE INTO health_metrics 
                                (patient_id, metric_name, value, unit, timestamp, date, 
                                 source_name, automation_type, session_id, raw_data)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''', (patient_id, metric_name, value, unit, mysql_timestamp, date_str,
                                  source_name, automation_type, session_id, json.dumps(item)))
                            
                            processed_other += 1
                            
                        except pymysql.Error as e:
                            logger.warning(f"Database error inserting health metric: {e}")
                            continue
                        
                except Exception as e:
                    logger.warning(f"Error processing individual metric: {e}")
                    continue
            
            conn.commit()
            
            result = {
                "status": "success",
                "processed_glucose_readings": processed_glucose,
                "processed_other_metrics": processed_other,
                "patient_id": patient_id,
                "session_id": session_id,
                "automation_type": automation_type,
                "timestamp": datetime.now().isoformat()
            }
            
            if processed_glucose > 0:
                logger.info(f"✅ Stored {processed_glucose} CGM readings")
            if processed_other > 0:
                logger.info(f"✅ Stored {processed_other} other health metrics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing CGM data: {e}")
            if conn:
                conn.rollback()
            return {"status": "error", "message": str(e), "patient_id": patient_id}
        finally:
            if conn:
                conn.close()
    
    def get_recent_cgm_readings(self, patient_id: str = "cgm_patient", minutes_back: int = 60) -> List[Dict]:
        """Get recent CGM readings (optimized for 5-minute frequency)"""
        conn = None
        try:
            conn = self.db_config.get_connection()
            cursor = conn.cursor()
            
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=minutes_back)
            
            cursor.execute('''
                SELECT timestamp, glucose_mg_dl, source_name, automation_type
                FROM cgm_readings 
                WHERE patient_id = %s 
                  AND timestamp >= %s
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (patient_id, start_time))
            
            results = cursor.fetchall()
            
            readings = []
            for row in results:
                timestamp = row['timestamp']
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.isoformat()
                    timestamp_dt = timestamp
                else:
                    timestamp_str = str(timestamp)
                    timestamp_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                readings.append({
                    "timestamp": timestamp_str,
                    "glucose_mg_dl": float(row['glucose_mg_dl']) if row['glucose_mg_dl'] is not None else None,
                    "source": row['source_name'],
                    "automation_type": row['automation_type'],
                    "minutes_ago": round((end_time - timestamp_dt).total_seconds() / 60, 1)
                })
            
            return readings
        except Exception as e:
            logger.error(f"Error getting recent CGM readings: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_cgm_stats(self, patient_id: str = "cgm_patient", hours_back: int = 24) -> Dict:
        """Get CGM statistics for the specified time period"""
        conn = None
        try:
            conn = self.db_config.get_connection()
            cursor = conn.cursor()
            
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            
            cursor.execute('''
                SELECT COUNT(*) as count, AVG(glucose_mg_dl) as avg_glucose, 
                       MIN(glucose_mg_dl) as min_glucose, MAX(glucose_mg_dl) as max_glucose,
                       MIN(timestamp) as first_reading, MAX(timestamp) as last_reading
                FROM cgm_readings 
                WHERE patient_id = %s 
                  AND timestamp >= %s
            ''', (patient_id, start_time))
            
            result = cursor.fetchone()
            
            if result and result['count'] > 0:
                count = result['count']
                avg_glucose = float(result['avg_glucose']) if result['avg_glucose'] else 0
                min_glucose = float(result['min_glucose']) if result['min_glucose'] else 0
                max_glucose = float(result['max_glucose']) if result['max_glucose'] else 0
                first_reading = result['first_reading']
                last_reading = result['last_reading']
                
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
                    "first_reading_time": first_reading.isoformat() if isinstance(first_reading, datetime) else str(first_reading),
                    "last_reading_time": last_reading.isoformat() if isinstance(last_reading, datetime) else str(last_reading),
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
            if conn:
                conn.close()

# Initialize CGM receiver
cgm_receiver = HighFrequencyCGMReceiver()

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
        result = cgm_receiver.process_cgm_data(
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
        stats_1h = cgm_receiver.get_cgm_stats(hours_back=1)
        stats_24h = cgm_receiver.get_cgm_stats(hours_back=24)
        recent_readings = cgm_receiver.get_recent_cgm_readings(minutes_back=30)
        
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
    """Run Flask server for CGM data reception"""
    logger.info(f"🏥 Starting 5-Minute CGM Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

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
        readings = cgm_receiver.get_recent_cgm_readings(minutes_back=minutes_back)
        
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
        stats_1h = cgm_receiver.get_cgm_stats(hours_back=1)
        stats_24h = cgm_receiver.get_cgm_stats(hours_back=24)
        recent_readings = cgm_receiver.get_recent_cgm_readings(minutes_back=15)
        
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

if __name__ == "__main__":
    # When running as MCP server, all output must go to stderr, not stdout
    # MCP communicates via JSON on stdout, so any print() will break it
    logger.info("🩸 Starting 5-Minute CGM Monitoring System...")
    logger.info("=" * 50)
    
    # Start Flask server
    flask_thread = threading.Thread(target=run_flask_server, args=(5000,), daemon=True)
    flask_thread.start()
    
    # Get and display server information
    server_ip = get_server_url()
    
    logger.info(f"✅ CGM Server Started Successfully!")
    logger.info(f"📡 Data Endpoint: http://{server_ip}:5000/health-data")
    logger.info(f"📊 Status Page: http://{server_ip}:5000/cgm-status") 
    logger.info(f"🔗 Local Status: http://localhost:5000/cgm-status")
    logger.info("=" * 50)
    logger.info("📱 Health Auto Export Configuration:")
    logger.info(f"   URL: http://{server_ip}:5000/health-data")
    logger.info(f"   Frequency: Quantity=5, Interval=minutes")
    logger.info(f"   Data: Blood Glucose only")
    logger.info(f"   Format: JSON")
    logger.info("=" * 50)
    logger.info("🚀 Starting MCP server...")
    
    # Start MCP server
    mcp.run(transport='stdio')