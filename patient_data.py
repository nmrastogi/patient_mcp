import pandas as pd
from typing import Union, Dict, Any

# Load only the necessary columns
PATIENT_DATA = pd.read_csv(
    "CSV_RastogiNaman_1260244_06Jul2025_2046.csv",header=1,skiprows=range(1,6),nrows=8624, 
    usecols=['SerialNumber', 'EventDateTime', 'Readings (mg/dL)']
)

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
        
        if patient_data.empty:
            return {"summary": f"No data found for SerialNumber {serial_number} between {start_date} and {end_date}"}

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
        
        result = fetch_patient_summary(first_serial)
        print(f"Result keys: {list(result.keys())}")
        
        if 'readings' in result:
            print(f"Number of readings: {len(result['readings'])}")
        if 'summary' in result:
            print(f"Has summary: Yes")
    else:
        print("❌ No data loaded from CSV")