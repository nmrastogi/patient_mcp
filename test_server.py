from patient_data import fetch_patient_summary

def test_fetch_patient_summary():
    result = fetch_patient_summary("12345")
    assert "summary" in result
    assert "John Doe" in result["summary"]

def test_invalid_patient():
    result = fetch_patient_summary("00000")
    assert "No data found" in result["summary"]

if __name__ == "__main__":
    print("Running tests...")
    test_fetch_patient_summary()
    test_invalid_patient()
    print("All tests passed! 🎉")