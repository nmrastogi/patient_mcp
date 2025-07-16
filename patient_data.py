import pandas as pd

# Load only the necessary columns
PATIENT_DATA = pd.read_csv(
    "patients.csv",header=1,skiprows=range(1,6),nrows=8620, 
    usecols=['SerialNumber', 'EventDateTime', 'Readings (mg/dL)']
)

def fetch_patient_summary(serial_number: str) -> dict:
    """
    Summarizes readings for a given SerialNumber from loaded CSV data.
    """
    patient_data = PATIENT_DATA[PATIENT_DATA['SerialNumber'] == serial_number]

    if patient_data.empty:
        return {"summary": f"No data found for SerialNumber {serial_number}"}

    num_readings = len(patient_data)
    avg_reading = patient_data['Readings (mg/dL)'].mean()
    latest_reading = patient_data.sort_values('EventDateTime', ascending=False).iloc[0]

    summary = (
        f"SerialNumber {serial_number} has {num_readings} readings. "
        f"Average reading: {avg_reading:.2f} mg/dL. "
        f"Most recent reading: {latest_reading['Readings (mg/dL)']} mg/dL on {latest_reading['EventDateTime']}."
    )

    return {"summary": summary}
