import pandas as pd

# Load only the necessary columns
PATIENT_DATA = pd.read_csv(
    "CSV_RastogiNaman_1260244_06Jul2025_2046.csv",header=1,skiprows=range(1,6),nrows=8624, 
    usecols=['SerialNumber', 'EventDateTime', 'Readings (mg/dL)']
)

def fetch_patient_summary(serial_number: int) -> dict:
    """
    Returns raw readings for a given SerialNumber from loaded CSV data.
    """
    patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == serial_number]

    if patient_data.empty:
        return {"summary": f"No data found for SerialNumber {serial_number}"}

    # Convert dataframe to list of dicts
    readings = patient_data[['EventDateTime', 'Readings (mg/dL)']].to_dict(orient='records')

    return {
        "serial_number": serial_number,
        "readings": readings
    }
