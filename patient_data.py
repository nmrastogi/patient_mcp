def fetch_patient_summary(patient_id: str) -> dict:
    # Example mocked data
    patient_db = {
        "12345": {
            "name": "John Doe",
            "age": 70,
            "diagnosis": "Type 2 Diabetes, Hypertension",
            "medications": ["Metformin", "Amlodipine"],
            "last_visit": "2025-06-20"
        }
    }

    patient = patient_db.get(patient_id)
    if not patient:
        return {"summary": f"No data found for patient ID {patient_id}"}

    summary = (
        f"Patient {patient['name']} (age {patient['age']}) last visited on {patient['last_visit']}. "
        f"Diagnosed with: {patient['diagnosis']}. "
        f"Current medications: {', '.join(patient['medications'])}."
    )

    return {"summary": summary}
