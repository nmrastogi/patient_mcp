import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Union, Dict, Any

# Load only the necessary columns
PATIENT_DATA = pd.read_csv(
    "CSV_RastogiNaman_1260244_06Jul2025_2046.csv",header=1,skiprows=range(1,6),nrows=8624, 
    usecols=['SerialNumber', 'EventDateTime', 'Readings (mg/dL)']
)
#Preprocessing
if not PATIENT_DATA.empty:
    PATIENT_DATA['EventDateTime'] = pd.to_datetime(PATIENT_DATA['EventDateTime'])
    PATIENT_DATA = PATIENT_DATA.sort_values(['SerialNumber', 'EventDateTime'])
    # Remove any invalid glucose readings
    PATIENT_DATA = PATIENT_DATA[PATIENT_DATA['Readings (mg/dL)'].notna()]

def fetch_patient_summary(patient_id: Union[int, str], start_date: str = None, end_date: str = None) -> dict:
    """
    Returns filtered readings for a given SerialNumber and optional date range.
    """
    try:
        serial_number = int(patient_id)
    except (ValueError, TypeError):
        return {"summary": f"Invalid patient ID format: {patient_id}"}
    
    patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == serial_number]

    if patient_data.empty:
        return {"summary": f"No data found for SerialNumber {serial_number}"}

    # Convert EventDateTime to datetime if not already
    patient_data = patient_data.copy()
    patient_data['EventDateTime'] = pd.to_datetime(patient_data['EventDateTime'])
    
    # Apply date filtering if provided
    if start_date and end_date:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # Include end date
        patient_data = patient_data[
            (patient_data['EventDateTime'] >= start_dt) & 
            (patient_data['EventDateTime'] < end_dt)
        ]
        
        # if patient_data.empty:
            # return {"summary": f"No data found for SerialNumber {serial_number} between {start_date} and {end_date}"}

    # Convert dataframe to list of dicts
    readings = patient_data[['EventDateTime', 'Readings (mg/dL)']].to_dict(orient='records')
    
    # Format dates
    for reading in readings:
        reading['EventDateTime'] = reading['EventDateTime'].isoformat()

    date_info = f" from {start_date} to {end_date}" if start_date and end_date else ""
    
    return {
        "serial_number": serial_number,
        "date_range": date_info,
        "readings": readings,
        "total_readings": len(readings)
    }
def detect_anomalous_glucose_events(patient_id: Union[int, str], days_back: int = 30, threshold_factor: float = 2.5) -> dict:
    """
    Detect anomalous glucose readings based on statistical analysis.
    Since you don't have insulin data yet, we'll focus on glucose anomalies.
    """
    try:
        serial_number = int(patient_id)
    except (ValueError, TypeError):
        return {"error": f"Invalid patient ID format: {patient_id}"}
    
    # Get recent data
    cutoff_date = datetime.now() - timedelta(days=days_back)
    patient_data = PATIENT_DATA[
        (PATIENT_DATA['SerialNumber'] == serial_number) & 
        (PATIENT_DATA['EventDateTime'] >= cutoff_date)
    ].copy()
    
    if patient_data.empty:
        return {"error": f"No recent data found for SerialNumber {serial_number}"}
    
    glucose_values = patient_data['Readings (mg/dL)']
    mean_glucose = glucose_values.mean()
    std_glucose = glucose_values.std()
    
    # Define anomalies as readings beyond threshold_factor standard deviations
    upper_threshold = mean_glucose + (threshold_factor * std_glucose)
    lower_threshold = mean_glucose - (threshold_factor * std_glucose)
    
    # Find anomalous readings
    anomalous_high = patient_data[patient_data['Readings (mg/dL)'] > upper_threshold]
    anomalous_low = patient_data[patient_data['Readings (mg/dL)'] < lower_threshold]
    
    anomalies = []
    for _, record in anomalous_high.iterrows():
        anomalies.append({
            "timestamp": record['EventDateTime'].isoformat(),
            "glucose_value": float(record['Readings (mg/dL)']),
            "anomaly_type": "high",
            "deviation_factor": float((record['Readings (mg/dL)'] - mean_glucose) / std_glucose),
            "severity": "severe" if record['Readings (mg/dL)'] > mean_glucose + (3 * std_glucose) else "moderate"
        })
    
    # Process low anomalies
    for _, record in anomalous_low.iterrows():
        anomalies.append({
            "timestamp": record['EventDateTime'].isoformat(),
            "glucose_value": float(record['Readings (mg/dL)']),
            "anomaly_type": "low", 
            "deviation_factor": float((record['Readings (mg/dL)'] - mean_glucose) / std_glucose),
            "severity": "severe" if record['Readings (mg/dL)'] < mean_glucose - (3 * std_glucose) else "moderate"
        })
    
    # Sort by timestamp
    anomalies.sort(key=lambda x: x['timestamp'])
    
    return {
        "patient_id": serial_number,
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
    try:
        serial_number = int(patient_id)
    except (ValueError, TypeError):
        return {"error": f"Invalid patient ID format: {patient_id}"}
    
    patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == serial_number].copy()
    
    if patient_data.empty:
        return {"error": f"No data found for SerialNumber {serial_number}"}
    
    # Find hypoglycemic events
    hypo_events = patient_data[patient_data['Readings (mg/dL)'] < glucose_threshold]
    
    if hypo_events.empty:
        return {
            "patient_id": serial_number,
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
        "patient_id": serial_number,
        "last_hypo_event": {
            "timestamp": event_time.isoformat(),
            "glucose_value": float(last_hypo['Readings (mg/dL)']),
            "days_ago": days_ago,
            "hours_ago": round((datetime.now() - event_time.replace(tzinfo=None)).total_seconds() / 3600, 1),
            "trend_before_event": trend_before,
            "recovery": recovery_info
        }
    }

def analyze_glucose_patterns(patient_id: Union[int, str], analysis_days: int = 14) -> dict:
    """
    Analyze daily glucose patterns to identify when sugar typically rises and falls.
    """
    try:
        serial_number = int(patient_id)
    except (ValueError, TypeError):
        return {"error": f"Invalid patient ID format: {patient_id}"}
    
    # Get recent data
    cutoff_date = datetime.now() - timedelta(days=analysis_days)
    patient_data = PATIENT_DATA[
        (PATIENT_DATA['SerialNumber'] == serial_number) & 
        (PATIENT_DATA['EventDateTime'] >= cutoff_date)
    ].copy()
    
    if patient_data.empty:
        return {"error": f"No recent data found for SerialNumber {serial_number}"}
    
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
        "patient_id": serial_number,
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
    total_readings = len(glucose_series)
    
    if total_readings == 0:
        return {}
    
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
# Add this at the very end of your patient_data.py file
if __name__ == "__main__":
    print("=== Testing Patient Data Module ===")
    
    # Test CSV loading
    print(f"CSV loaded: {not PATIENT_DATA.empty}")
    print(f"Total rows: {len(PATIENT_DATA)}")
    
    if not PATIENT_DATA.empty:
        print(f"Columns: {list(PATIENT_DATA.columns)}")
        print(f"Unique SerialNumbers: {PATIENT_DATA['SerialNumber'].unique()}")
        
        # Test with first available SerialNumber
        first_serial = PATIENT_DATA['SerialNumber'].iloc[0]
        print(f"\nTesting with SerialNumber: {first_serial}")
        
        # Test all functions
        print("\n1. Testing basic summary:")
        result = fetch_patient_summary(first_serial)
        print(f"Readings found: {result.get('total_readings', 0)}")
        
        print("\n2. Testing anomaly detection:")
        anomalies = detect_anomalous_glucose_events(first_serial)
        print(f"Anomalies found: {anomalies.get('total_anomalies', 0)}")
        
        print("\n3. Testing hypo detection:")
        hypo = find_last_hypoglycemic_event(first_serial)
        if hypo.get('last_hypo_event'):
            print(f"Last hypo: {hypo['last_hypo_event']['days_ago']} days ago")
        else:
            print("No hypo events found")
        
        print("\n4. Testing pattern analysis:")
        patterns = analyze_glucose_patterns(first_serial)
        if 'peak_glucose_time' in patterns:
            print(f"Peak glucose time: {patterns['peak_glucose_time']}")
            print(f"Dawn phenomenon: {patterns['dawn_phenomenon']['detected']}")
    else:
        print("❌ No data loaded from CSV")