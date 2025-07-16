#!/usr/bin/env python3
"""
Test your MCP server manually
"""

import subprocess
import sys
import json
import time

def test_server_manually():
    """Test the MCP server by sending JSON-RPC messages directly"""
    print("=== Testing MCP Server Manually ===")
    
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

        # Step 2: List available tools
        print("2. Requesting tools list...")
        tools_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()
        time.sleep(1)

        # Step 3: Call the get_patient_summary tool
        print("3. Calling get_patient_summary tool...")
        tool_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_patient_summary",
                "arguments": {
                    "patient_id": 1260244  # Replace with your actual SerialNumber
                }
            }
        }
        process.stdin.write(json.dumps(tool_msg) + "\n")
        process.stdin.flush()
        time.sleep(2)

        # Step 4: Read and display server responses
        print("4. Checking for responses...")
        for _ in range(5):  # Read up to 5 lines of output
            output_line = process.stdout.readline()
            if output_line:
                print(output_line.strip())
            time.sleep(0.5)

        if process.poll() is None:
            print("✓ Server is running and accepted messages")
        else:
            print("❌ Server stopped unexpectedly")

        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"Server errors: {stderr_output}")
        else:
            print("✓ No errors in stderr")

    except Exception as e:
        print(f"Error during test: {e}")
    
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    test_server_manually()
    print("\nTo test your server interactively, run:")
    print("python server.py")
    print("Then paste JSON messages manually.")
