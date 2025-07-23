#!/usr/bin/env python3
"""
Test your MCP server manually with JSON data
"""

import subprocess
import sys
import json
import time

def test_server_manually():
    """Test the MCP server by sending JSON-RPC messages directly"""
    print("=== Testing MCP Server Manually (JSON Version) ===")
    
    # Start the MCP server
    process = subprocess.Popen(
        [sys.executable, "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Step 1: Initialize the server
        print("1. Sending initialization message...")
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        time.sleep(1)

        # Step 2: Send initialized notification
        print("2. Sending initialized notification...")
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        process.stdin.write(json.dumps(initialized_msg) + "\n")
        process.stdin.flush()
        time.sleep(0.5)

        # Step 3: List available tools
        print("3. Requesting tools list...")
        tools_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()
        time.sleep(1)

        # Step 4: Get available patients first
        print("4. Getting available patients...")
        patients_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_available_patients",
                "arguments": {}
            }
        }
        process.stdin.write(json.dumps(patients_msg) + "\n")
        process.stdin.flush()
        time.sleep(2)

        # Step 5: Test patient summary (you'll need to replace with actual patient ID)
        print("5. Testing patient summary...")
        summary_msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_patient_summary",
                "arguments": {
                    "patient_id": "YOUR_PATIENT_ID_HERE"  # Replace with actual ID from step 4
                }
            }
        }
        process.stdin.write(json.dumps(summary_msg) + "\n")
        process.stdin.flush()
        time.sleep(2)

        # Step 6: Test anomaly detection
        print("6. Testing anomaly detection...")
        anomaly_msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_anomalous_events",
                "arguments": {
                    "patient_id": "YOUR_PATIENT_ID_HERE",  # Replace with actual ID
                    "days_back": 14
                }
            }
        }
        process.stdin.write(json.dumps(anomaly_msg) + "\n")
        process.stdin.flush()
        time.sleep(2)

        # Step 7: Test comprehensive report
        print("7. Testing comprehensive report...")
        report_msg = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_comprehensive_diabetes_report",
                "arguments": {
                    "patient_id": "YOUR_PATIENT_ID_HERE",  # Replace with actual ID
                    "analysis_days": 14
                }
            }
        }
        process.stdin.write(json.dumps(report_msg) + "\n")
        process.stdin.flush()
        time.sleep(3)

        # Step 8: Read and display server responses
        print("8. Reading server responses...")
        print("=" * 50)
        
        for i in range(10):  # Read up to 10 lines of output
            try:
                output_line = process.stdout.readline()
                if output_line:
                    print(f"Response {i+1}: {output_line.strip()}")
                    
                    # Try to parse as JSON for prettier display
                    try:
                        response_data = json.loads(output_line.strip())
                        print(f"Parsed JSON: {json.dumps(response_data, indent=2)}")
                    except:
                        pass
                        
                time.sleep(0.5)
            except:
                break

        if process.poll() is None:
            print("✓ Server is running and accepted messages")
        else:
            print("❌ Server stopped unexpectedly")

        # Check for errors
        try:
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"\nServer stderr output:")
                print(stderr_output)
            else:
                print("✓ No errors in stderr")
        except:
            pass

    except Exception as e:
        print(f"Error during test: {e}")
    
    finally:
        process.terminate()
        process.wait()

def test_data_loading_first():
    """Test data loading before testing the server"""
    print("=== Testing Data Loading First ===")
    
    try:
        # Test the patient_data module directly
        from patient_data import get_available_patients, fetch_patient_summary
        
        print("1. Testing data loading...")
        patients = get_available_patients()
        
        if patients:
            print(f"✓ Found {len(patients)} patients: {patients[:5]}...")  # Show first 5
            
            # Test with first patient
            first_patient = patients[0]
            print(f"2. Testing with patient ID: {first_patient}")
            
            summary = fetch_patient_summary(first_patient)
            print(f"✓ Patient summary loaded: {summary.get('total_readings', 0)} readings")
            
            return first_patient
        else:
            print("❌ No patients found. Check your JSON file.")
            return None
            
    except Exception as e:
        print(f"❌ Error testing data: {e}")
        return None

def run_interactive_test():
    """Run an interactive test where you can specify patient ID"""
    print("=== Interactive MCP Server Test ===")
    
    # First check data loading
    test_patient = test_data_loading_first()
    
    if not test_patient:
        print("\nData loading failed. Please check:")
        print("1. JSON file exists: TidepoolExport_jan25_july25.json")
        print("2. JSON file has valid data")
        print("3. File path is correct in patient_data.py")
        return
    
    print(f"\nUsing patient ID: {test_patient}")
    choice = input("Use this patient ID? (y/n): ").lower()
    
    if choice != 'y':
        custom_id = input("Enter patient ID to test with: ")
        test_patient = custom_id
    
    # Now test the server with the chosen patient ID
    print(f"\nTesting server with patient ID: {test_patient}")
    test_server_with_patient_id(test_patient)

def test_server_with_patient_id(patient_id):
    """Test server with a specific patient ID"""
    print(f"=== Testing MCP Server with Patient {patient_id} ===")
    
    process = subprocess.Popen(
        [sys.executable, "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Initialize
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        time.sleep(1)
        
        # Initialized notification
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()
        time.sleep(0.5)
        
        # Test patient summary
        print("Testing patient summary...")
        summary_msg = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_patient_summary", "arguments": {"patient_id": patient_id}}
        }
        process.stdin.write(json.dumps(summary_msg) + "\n")
        process.stdin.flush()
        time.sleep(2)
        
        # Test anomalies
        print("Testing anomaly detection...")
        anomaly_msg = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "get_anomalous_events", "arguments": {"patient_id": patient_id, "days_back": 7}}
        }
        process.stdin.write(json.dumps(anomaly_msg) + "\n")
        process.stdin.flush()
        time.sleep(2)
        
        # Read responses
        print("\nServer Responses:")
        print("=" * 40)
        for i in range(5):
            try:
                response = process.stdout.readline()
                if response:
                    print(f"Response {i+1}: {response.strip()}")
            except:
                break
            time.sleep(0.5)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    print("MCP Server Test Suite (JSON Version)")
    print("=" * 50)
    
    print("\nChoose test method:")
    print("1. Interactive test (recommended)")
    print("2. Manual server test")
    print("3. Data loading test only")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        run_interactive_test()
    elif choice == "2":
        test_server_manually()
    elif choice == "3":
        test_data_loading_first()
    else:
        print("Invalid choice. Running interactive test...")
        run_interactive_test()
    
    print("\n" + "=" * 50)
    print("Test complete!")
    print("\nNext steps:")
    print("1. If tests passed, your server is ready for Claude MCP")
    print("2. If tests failed, check the error messages above")
    print("3. Make sure your JSON file path is correct")