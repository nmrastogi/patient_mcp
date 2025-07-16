from patient_data import fetch_patient_summary

def test_valid_serial_number():
    serial_number = "YOUR_VALID_SERIAL_NUMBER"  # Replace with actual SerialNumber from your CSV
    result = fetch_patient_summary(serial_number)
    print(result)
    assert "summary" in result
    assert f"SerialNumber {serial_number}" in result["summary"]

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
