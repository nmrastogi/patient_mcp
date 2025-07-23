import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import Union, Dict, Any, List

# Global variable to hold patient data
PATIENT_DATA = pd.DataFrame()

def load_json_data(json_file_path: str = "TidepoolExport_jan25_july25.json") -> pd.DataFrame:
    """
    Load and process JSON data from Tidepool export format
    """
    global PATIENT_DATA
    
    try:
        # Load JSON data
        with open(json_file_path, 'r') as f:
            json_data = json.load(f)
        
        # Convert to DataFrame
        df = pd.DataFrame(json_data)
        
        if df.empty:
            print("Warning: JSON file is empty")
            return df
            
        print(f"Loaded {len(df)} records from JSON")
        print(f"Data types found: {df['type'].value_counts().to_dict()}")
        
        # Process timestamps with robust format handling
        if 'time' in df.columns:
            try:
                # Try ISO8601 format first (handles Z suffix properly)
                df['time'] = pd.to_datetime(df['time'], format='ISO8601')
            except:
                try:
                    # Fallback to mixed format parsing
                    df['time'] = pd.to_datetime(df['time'], format='mixed')
                except:
                    # Last resort - let pandas infer
                    df['time'] = pd.to_datetime(df['time'], utc=True)
        
        # Create standardized columns for glucose data
        df['glucose_value'] = None
        df['insulin_bolus'] = None
        df['insulin_basal_rate'] = None
        df['patient_id'] = None  # We'll need to derive this somehow
        
        # Process different data types
        processed_records = []
        
        for _, row in df.iterrows():
            record = row.to_dict()
            data_type = row.get('type', '')
            
            # Process glucose readings (CGM and fingerstick)
            if data_type == 'cbg':  # Continuous glucose monitor
                record['glucose_value'] = row.get('value')
                record['data_source'] = 'cgm'
                record['SerialNumber'] = 'patient_001'
            elif data_type == 'smbg':  # Self-monitored blood glucose
                record['glucose_value'] = row.get('value')
                record['data_source'] = 'fingerstick'
                record['SerialNumber'] = 'patient_001'
            
            # Process insulin data
            elif data_type == 'bolus':
                record['insulin_bolus'] = row.get('normal', 0) + row.get('extended', 0)
                record['SerialNumber'] = 'patient_001'
            elif data_type == 'basal':
                record['insulin_basal_rate'] = row.get('rate', 0)
                record['SerialNumber'] = 'patient_001'
            
            # Add standardized timestamp
            record['EventDateTime'] = row.get('time')
            record['Readings (mg/dL)'] = record.get('glucose_value')
            
            processed_records.append(record)
        
        # Create processed DataFrame
        PATIENT_DATA = pd.DataFrame(processed_records)
        
        # Filter to only glucose readings for compatibility with existing functions
        glucose_data = PATIENT_DATA[PATIENT_DATA['glucose_value'].notna()].copy()
        
        if not glucose_data.empty:
            glucose_data = glucose_data.sort_values(['SerialNumber', 'EventDateTime'])
            # Remove any invalid glucose readings
            glucose_data = glucose_data[glucose_data['glucose_value'].notna()]
            
            # Update the global variable with glucose data
            PATIENT_DATA = glucose_data[['SerialNumber', 'EventDateTime', 'Readings (mg/dL)', 'data_source', 'type']].copy()
            
        print(f"Processed {len(PATIENT_DATA)} glucose records")
        print(f"Unique patients/devices: {PATIENT_DATA['SerialNumber'].nunique()}")
        
        return PATIENT_DATA
        
    except FileNotFoundError:
        print(f"Error: JSON file '{json_file_path}' not found")
        return pd.DataFrame()
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading JSON data: {e}")
        return pd.DataFrame()

def get_available_patients() -> List[str]:
    """Get list of available patient/device IDs"""
    if PATIENT_DATA.empty:
        load_json_data()
    
    if not PATIENT_DATA.empty and 'SerialNumber' in PATIENT_DATA.columns:
        return sorted(PATIENT_DATA['SerialNumber'].unique().tolist())
    return []

def fetch_patient_summary(patient_id: Union[int, str], start_date: str = None, end_date: str = None) -> dict:
    """
    Returns filtered readings for a given SerialNumber and optional date range.
    """
    global PATIENT_DATA
    
    # Load data if not already loaded
    if PATIENT_DATA.empty:
        PATIENT_DATA = load_json_data()
    
    if PATIENT_DATA.empty:
        return {"summary": "No data available. Please check JSON file."}
    
    try:
        # Convert patient_id to string for comparison (since JSON might have string IDs)
        patient_id_str = str(patient_id)
        
        # Try both string and numeric matching
        patient_data = PATIENT_DATA[
            (PATIENT_DATA['SerialNumber'].astype(str) == patient_id_str) |
            (PATIENT_DATA['SerialNumber'] == patient_id)
        ]
        
    except (ValueError, TypeError):
        return {"summary": f"Invalid patient ID format: {patient_id}"}
    
    if patient_data.empty:
        available_patients = get_available_patients()
        return {
            "summary": f"No data found for patient ID {patient_id}",
            "available_patients": available_patients[:10]  # Show first 10 available IDs
        }

    # Convert EventDateTime to datetime if not already
    patient_data = patient_data.copy()
    if 'EventDateTime' in patient_data.columns:
        try:
            patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], format='ISO8601')
        except:
            try:
                patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], format='mixed')
            except:
                patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], utc=True)
    
    # Apply date filtering if provided
    if start_date and end_date:
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # Include end date
            patient_data = patient_data[
                (patient_data['EventDateTime'] >= start_dt) & 
                (patient_data['EventDateTime'] < end_dt)
            ]
        except Exception as e:
            return {"summary": f"Invalid date format. Use YYYY-MM-DD. Error: {e}"}
        
    # Convert dataframe to list of dicts
    readings = []
    for _, row in patient_data.iterrows():
        reading = {
            'EventDateTime': row['EventDateTime'].isoformat() if pd.notna(row['EventDateTime']) else None,
            'Readings (mg/dL)': row['Readings (mg/dL)'] if pd.notna(row['Readings (mg/dL)']) else None,
            'data_source': row.get('data_source', 'unknown'),
            'type': row.get('type', 'unknown')
        }
        readings.append(reading)

    date_info = f" from {start_date} to {end_date}" if start_date and end_date else ""
    
    return {
        "patient_id": patient_id,
        "date_range": date_info,
        "readings": readings,
        "total_readings": len(readings),
        "data_sources": patient_data['data_source'].value_counts().to_dict() if 'data_source' in patient_data.columns else {}
    }

def detect_anomalous_glucose_events(patient_id: Union[int, str], days_back: int = 30, threshold_factor: float = 2.5) -> dict:
    """
    Detect anomalous glucose readings based on statistical analysis.
    """
    global PATIENT_DATA
    
    if PATIENT_DATA.empty:
        PATIENT_DATA = load_json_data()
    
    try:
        patient_id_str = str(patient_id)
        
        # Get patient data first
        patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == patient_id_str].copy()
        
        if not patient_data.empty:
            # Parse timestamps and filter by date
            patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], utc=True)
            cutoff_date = pd.Timestamp.now(tz='UTC') - timedelta(days=days_back)
            patient_data = patient_data[patient_data['EventDateTime'] >= cutoff_date]
        
    except Exception as e:
        return {"error": f"Error processing patient {patient_id}: {str(e)}"}
    
    if patient_data.empty:
        return {
            "error": f"No recent data found for patient {patient_id}",
            "patient_id": patient_id,
            "total_anomalies": 0,
            "anomalous_events": []
        }
    
    glucose_values = patient_data['Readings (mg/dL)'].dropna()
    if len(glucose_values) < 5:
        return {
            "error": "Insufficient data for anomaly detection",
            "patient_id": patient_id,
            "total_anomalies": 0,
            "anomalous_events": []
        }
    
    mean_glucose = glucose_values.mean()
    std_glucose = glucose_values.std()
    
    # Define anomalies as readings beyond threshold_factor standard deviations
    upper_threshold = mean_glucose + (threshold_factor * std_glucose)
    lower_threshold = mean_glucose - (threshold_factor * std_glucose)
    
    # Find anomalous readings
    anomalous_high = patient_data[patient_data['Readings (mg/dL)'] > upper_threshold]
    anomalous_low = patient_data[patient_data['Readings (mg/dL)'] < lower_threshold]
    
    anomalies = []
    
    # Process high anomalies
    for _, record in anomalous_high.iterrows():
        if pd.notna(record['Readings (mg/dL)']):
            anomalies.append({
                "timestamp": record['EventDateTime'].isoformat(),
                "glucose_value": float(record['Readings (mg/dL)']),
                "anomaly_type": "high",
                "deviation_factor": float((record['Readings (mg/dL)'] - mean_glucose) / std_glucose),
                "severity": "severe" if record['Readings (mg/dL)'] > mean_glucose + (3 * std_glucose) else "moderate",
                "data_source": record.get('data_source', 'unknown')
            })
    
    # Process low anomalies
    for _, record in anomalous_low.iterrows():
        if pd.notna(record['Readings (mg/dL)']):
            anomalies.append({
                "timestamp": record['EventDateTime'].isoformat(),
                "glucose_value": float(record['Readings (mg/dL)']),
                "anomaly_type": "low", 
                "deviation_factor": float((record['Readings (mg/dL)'] - mean_glucose) / std_glucose),
                "severity": "severe" if record['Readings (mg/dL)'] < mean_glucose - (3 * std_glucose) else "moderate",
                "data_source": record.get('data_source', 'unknown')
            })
    
    # Sort by timestamp
    anomalies.sort(key=lambda x: x['timestamp'])
    
    return {
        "patient_id": patient_id,
        "analysis_period": f"Last {days_back} days",
        "total_anomalies": len(anomalies),
        "baseline_stats": {
            "mean_glucose": round(mean_glucose, 1),
            "std_deviation": round(std_glucose, 1),
            "upper_threshold": round(upper_threshold, 1),
            "lower_threshold": round(lower_threshold, 1)
        },
        "anomalous_events": anomalies
    }

def find_last_hypoglycemic_event(patient_id: Union[int, str], glucose_threshold: float = 70) -> dict:
    """
    Find the most recent hypoglycemic event and analyze recovery.
    """
    global PATIENT_DATA
    
    if PATIENT_DATA.empty:
        PATIENT_DATA = load_json_data()
    
    try:
        patient_id_str = str(patient_id)
        patient_data = PATIENT_DATA[
            (PATIENT_DATA['SerialNumber'].astype(str) == patient_id_str) |
            (PATIENT_DATA['SerialNumber'] == patient_id)
        ].copy()
    except (ValueError, TypeError):
        return {"error": f"Invalid patient ID format: {patient_id}"}
    
    if patient_data.empty:
        return {"error": f"No data found for patient {patient_id}"}
    
    # Handle timestamp parsing
    try:
        patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], format='ISO8601')
    except:
        try:
            patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], format='mixed')
        except:
            patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], utc=True)
    
    # Find hypoglycemic events
    hypo_events = patient_data[patient_data['Readings (mg/dL)'] < glucose_threshold]
    
    if hypo_events.empty:
        return {
            "patient_id": patient_id,
            "message": f"No hypoglycemic events found below {glucose_threshold} mg/dL",
            "last_hypo_event": None
        }
    
    # Get the most recent hypoglycemic reading
    last_hypo = hypo_events.iloc[-1]
    event_time = last_hypo['EventDateTime']
    
    # Find recovery (next reading >= threshold after the hypo event)
    recovery_data = patient_data[
        (patient_data['EventDateTime'] > event_time) & 
        (patient_data['Readings (mg/dL)'] >= glucose_threshold)
    ]
    
    recovery_info = None
    if not recovery_data.empty:
        recovery_reading = recovery_data.iloc[0]
        duration_minutes = (recovery_reading['EventDateTime'] - event_time).total_seconds() / 60
        recovery_info = {
            "recovery_time": recovery_reading['EventDateTime'].isoformat(),
            "recovery_glucose": float(recovery_reading['Readings (mg/dL)']),
            "duration_minutes": round(duration_minutes, 1)
        }
    
    # Look for pattern before hypo (last 3 readings)
    readings_before = patient_data[patient_data['EventDateTime'] < event_time].tail(3)
    trend_before = "unknown"
    if len(readings_before) >= 2:
        glucose_trend = readings_before['Readings (mg/dL)'].diff().iloc[-1]
        if glucose_trend < -10:
            trend_before = "falling rapidly"
        elif glucose_trend < -5:
            trend_before = "falling"
        elif glucose_trend > 5:
            trend_before = "rising"
        else:
            trend_before = "stable"
    
    days_ago = (datetime.now() - event_time.replace(tzinfo=None)).days
    
    return {
        "patient_id": patient_id,
        "last_hypo_event": {
            "timestamp": event_time.isoformat(),
            "glucose_value": float(last_hypo['Readings (mg/dL)']),
            "days_ago": days_ago,
            "hours_ago": round((datetime.now() - event_time.replace(tzinfo=None)).total_seconds() / 3600, 1),
            "trend_before_event": trend_before,
            "recovery": recovery_info,
            "data_source": last_hypo.get('data_source', 'unknown')
        }
    }

def analyze_glucose_patterns(patient_id: Union[int, str], analysis_days: int = 14) -> dict:
    """
    Analyze daily glucose patterns to identify when sugar typically rises and falls.
    """
    global PATIENT_DATA
    
    if PATIENT_DATA.empty:
        PATIENT_DATA = load_json_data()
    
    try:
        patient_id_str = str(patient_id)
        
        # Get patient data first
        patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == patient_id_str].copy()
        
        if not patient_data.empty:
            # Parse timestamps and filter by date
            patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'], utc=True)
            cutoff_date = pd.Timestamp.now(tz='UTC') - timedelta(days=analysis_days)
            patient_data = patient_data[patient_data['EventDateTime'] >= cutoff_date]
        
    except Exception as e:
        return {"error": f"Error processing patient {patient_id}: {str(e)}"}
    
    if patient_data.empty:
        return {
            "error": f"No recent data found for patient {patient_id}",
            "patient_id": patient_id,
            "total_readings": 0
        }
    
    # Add time-based features
    patient_data['hour'] = patient_data['EventDateTime'].dt.hour
    patient_data['day_of_week'] = patient_data['EventDateTime'].dt.day_name()
    patient_data['date'] = patient_data['EventDateTime'].dt.date
    
    # Analyze hourly patterns
    hourly_stats = patient_data.groupby('hour')['Readings (mg/dL)'].agg([
        'mean', 'std', 'count', 'min', 'max'
    ]).round(1)
    
    hourly_patterns = {}
    for hour in hourly_stats.index:
        stats = hourly_stats.loc[hour]
        hourly_patterns[f"{hour:02d}:00"] = {
            "avg_glucose": float(stats['mean']),
            "std_deviation": float(stats['std']) if not pd.isna(stats['std']) else 0,
            "min_glucose": float(stats['min']),
            "max_glucose": float(stats['max']),
            "readings_count": int(stats['count'])
        }
    
    # Identify peak and trough times
    peak_hour = hourly_stats['mean'].idxmax()
    trough_hour = hourly_stats['mean'].idxmin()
    
    # Detect dawn phenomenon (glucose rise between 4-8 AM)
    dawn_hours = [4, 5, 6, 7, 8]
    dawn_data = hourly_stats.loc[hourly_stats.index.isin(dawn_hours)]
    dawn_phenomenon = False
    dawn_rise = 0
    
    if len(dawn_data) >= 3:
        early_morning = dawn_data.loc[4:6]['mean'].mean() if any(h in dawn_data.index for h in [4,5,6]) else None
        late_morning = dawn_data.loc[6:8]['mean'].mean() if any(h in dawn_data.index for h in [6,7,8]) else None
        
        if early_morning and late_morning:
            dawn_rise = late_morning - early_morning
            dawn_phenomenon = dawn_rise > 15  # Significant rise
    
    # Analyze day-to-day variability
    daily_avg = patient_data.groupby('date')['Readings (mg/dL)'].mean()
    glucose_variability = {
        "coefficient_of_variation": round((daily_avg.std() / daily_avg.mean()) * 100, 1),
        "daily_range_avg": round(daily_avg.max() - daily_avg.min(), 1)
    }
    
    return {
        "patient_id": patient_id,
        "analysis_period": f"Last {analysis_days} days",
        "total_readings": len(patient_data),
        "hourly_patterns": hourly_patterns,
        "peak_glucose_time": f"{peak_hour:02d}:00",
        "lowest_glucose_time": f"{trough_hour:02d}:00",
        "dawn_phenomenon": {
            "detected": dawn_phenomenon,
            "rise_amount": round(dawn_rise, 1) if dawn_rise else 0,
            "description": "Glucose rise between 4-8 AM typical of dawn phenomenon" if dawn_phenomenon else "No significant dawn phenomenon detected"
        },
        "glucose_variability": glucose_variability,
        "time_in_ranges": calculate_time_in_range(patient_data['Readings (mg/dL)'])
    }

def calculate_time_in_range(glucose_series: pd.Series) -> dict:
    """Calculate percentage of time in different glucose ranges."""
    glucose_series = glucose_series.dropna()
    total_readings = len(glucose_series)
    
    if total_readings == 0:
        return {
            "very_low_under_54": "0.0%",
            "low_54_to_70": "0.0%", 
            "target_70_to_180": "0.0%",
            "high_180_to_250": "0.0%",
            "very_high_over_250": "0.0%"
        }
    
    ranges = {
        "very_low": (glucose_series < 54).sum(),
        "low": ((glucose_series >= 54) & (glucose_series < 70)).sum(),
        "target_range": ((glucose_series >= 70) & (glucose_series <= 180)).sum(),
        "high": ((glucose_series > 180) & (glucose_series <= 250)).sum(),
        "very_high": (glucose_series > 250).sum()
    }
    
    percentages = {k: round((v / total_readings) * 100, 1) for k, v in ranges.items()}
    
    return {
        "very_low_under_54": f"{percentages['very_low']}%",
        "low_54_to_70": f"{percentages['low']}%", 
        "target_70_to_180": f"{percentages['target_range']}%",
        "high_180_to_250": f"{percentages['high']}%",
        "very_high_over_250": f"{percentages['very_high']}%"
    }

# Initialize data on import
print("Loading JSON data...")
try:
    PATIENT_DATA = load_json_data()
    if not PATIENT_DATA.empty:
        print(f"✓ Loaded data for {len(get_available_patients())} patients/devices")
    else:
        print("⚠ No data loaded - check JSON file")
except Exception as e:
    print(f"⚠ Error during initialization: {e}")

# Testing section
if __name__ == "__main__":
    print("=== Testing JSON Patient Data Module ===")
    
    # Test data loading
    print(f"Data loaded: {not PATIENT_DATA.empty}")
    print(f"Total glucose records: {len(PATIENT_DATA)}")
    
    if not PATIENT_DATA.empty:
        available_patients = get_available_patients()
        print(f"Available patients: {available_patients}")
        
        if available_patients:
            # Test with first available patient
            first_patient = available_patients[0]
            print(f"\nTesting with patient ID: {first_patient}")
            
            # Test all functions
            print("\n1. Testing basic summary:")
            result = fetch_patient_summary(first_patient)
            print(f"Readings found: {result.get('total_readings', 0)}")
            
            print("\n2. Testing anomaly detection:")
            anomalies = detect_anomalous_glucose_events(first_patient)
            print(f"Anomalies found: {anomalies.get('total_anomalies', 0)}")
            
            print("\n3. Testing hypo detection:")
            hypo = find_last_hypoglycemic_event(first_patient)
            if hypo.get('last_hypo_event'):
                print(f"Last hypo: {hypo['last_hypo_event']['days_ago']} days ago")
            else:
                print("No hypo events found")
            
            print("\n4. Testing pattern analysis:")
            patterns = analyze_glucose_patterns(first_patient)
            if 'peak_glucose_time' in patterns:
                print(f"Peak glucose time: {patterns['peak_glucose_time']}")
                print(f"Dawn phenomenon: {patterns['dawn_phenomenon']['detected']}")
        else:
            print("No patients found in data")
    else:
        print("❌ No data loaded from JSON")