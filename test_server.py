from patient_data import fetch_patient_summary

def test_valid_serial_number():
    serial_number = 1260244  # or as str if needed
    result = fetch_patient_summary(serial_number)
    print(result)
    assert "readings" in result
    assert isinstance(result["readings"], list)
    assert len(result["readings"]) > 0

def test_invalid_serial_number():
    serial_number = "NON_EXISTENT_SN"
    result = fetch_patient_summary(serial_number)
    print(result)
    assert "No data found" in result["summary"]

if __name__ == "__main__":
    print("Running tests...")
    test_valid_serial_number()
    test_invalid_serial_number()
    print("All tests passed! 🎉")
