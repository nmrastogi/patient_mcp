#!/usr/bin/env python3
"""
Test your server manually
"""

import subprocess
import sys
import json
import time

def test_server_manually():
    """Test the server by sending JSON-RPC messages directly"""
    print("=== Testing MCP Server Manually ===")
    
    # Start the server
    process = subprocess.Popen(
        [sys.executable, "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Test 1: Send initialization message
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
        
        # Wait a moment for response
        time.sleep(1)
        
        # Test 2: List tools
        print("2. Requesting tools list...")
        tools_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_patient_summary",
                "arguments": {
                "patient_id": "1260244",
                "mode": "raw"
        }
    }
}
        
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()
        
        time.sleep(1)
        
        # Test 3: Call the tool
        print("3. Calling get_patient_summary tool...")
        tool_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_patient_summary",
                "arguments": {
                    "patient_id": "12345"
                }
            }
        }
        
        process.stdin.write(json.dumps(tool_msg) + "\n")
        process.stdin.flush()
        
        time.sleep(2)
        
        # Try to read any output
        print("4. Checking for responses...")
        
        # Check if process is still running
        if process.poll() is None:
            print("✓ Server is running and accepting messages")
        else:
            print("❌ Server stopped")
            
        # Check stderr for any errors
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"Server errors: {stderr_output}")
        else:
            print("✓ No errors in stderr")
            
    except Exception as e:
        print(f"Error during test: {e}")
        
    finally:
        # Clean up
        process.terminate()
        process.wait()

if __name__ == "__main__":
    test_server_manually()
    print("\nTo test your server interactively, run:")
    print("python server.py")
    print("Then paste JSON messages manually.")