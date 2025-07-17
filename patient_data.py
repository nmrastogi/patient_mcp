import pandas as pd
from typing import Union, Dict, Any

# Load only the necessary columns
PATIENT_DATA = pd.read_csv(
    "CSV_RastogiNaman_1260244_06Jul2025_2046.csv",header=1,skiprows=range(1,6),nrows=8624, 
    usecols=['SerialNumber', 'EventDateTime', 'Readings (mg/dL)']
)

def fetch_patient_summary(patient_id: Union[int, str]) -> dict:
    """
    Returns raw readings for a given SerialNumber from loaded CSV data.
    """
    serial_number = int(patient_id)  # Convert to string for lookup
    patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == serial_number]

    if patient_data.empty:
        return {"summary": f"No data found for SerialNumber {serial_number}"}

    # Convert dataframe to list of dicts
    readings = patient_data[['EventDateTime', 'Readings (mg/dL)']].to_dict(orient='records')

    return {
        "serial_number": serial_number,
        "readings": readings
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