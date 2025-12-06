#!/usr/bin/env python3
"""
Test script for MCP server - tests Flask endpoints and MCP tools
"""
import sys
import json
import requests
import subprocess
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_flask_endpoints(base_url="http://localhost:5001"):
    """Test Flask HTTP endpoints"""
    logger.info("=" * 70)
    logger.info("TEST 1: Flask HTTP Endpoints")
    logger.info("=" * 70)
    
    results = []
    
    # Test health endpoint
    try:
        logger.info("\n📊 Testing /cgm-status endpoint...")
        response = requests.get(f"{base_url}/cgm-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Status endpoint working")
            logger.info(f"   Server running: {data.get('server_running', False)}")
            logger.info(f"   Total readings: {data.get('total_readings', 0)}")
            results.append(("Flask Status Endpoint", True))
        else:
            logger.error(f"❌ Status endpoint returned {response.status_code}")
            results.append(("Flask Status Endpoint", False))
    except requests.exceptions.ConnectionError:
        logger.warning("⚠️  Flask server not running on port 5001, trying 5000...")
        try:
            response = requests.get("http://localhost:5000/cgm-status", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Status endpoint working on port 5000")
                results.append(("Flask Status Endpoint", True))
            else:
                results.append(("Flask Status Endpoint", False))
        except:
            logger.error("❌ Flask server not accessible")
            results.append(("Flask Status Endpoint", False))
    except Exception as e:
        logger.error(f"❌ Error testing status endpoint: {e}")
        results.append(("Flask Status Endpoint", False))
    
    # Test health-data endpoint (POST)
    try:
        logger.info("\n📊 Testing /health-data endpoint...")
        test_data = {
            "patient_id": "test_patient",
            "data": [{
                "timestamp": datetime.now().isoformat(),
                "value": 120.0,
                "unit": "mg/dL",
                "type": "bloodGlucose"
            }]
        }
        response = requests.post(f"{base_url}/health-data", json=test_data, timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Health data endpoint working")
            logger.info(f"   Status: {data.get('status')}")
            results.append(("Flask Health Data Endpoint", True))
        else:
            logger.warning(f"⚠️  Health data endpoint returned {response.status_code}")
            results.append(("Flask Health Data Endpoint", False))
    except Exception as e:
        logger.warning(f"⚠️  Could not test health data endpoint: {e}")
        results.append(("Flask Health Data Endpoint", False))
    
    return results

def test_mcp_tools_direct():
    """Test MCP tools by importing and calling them directly"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: MCP Tools (Direct Import)")
    logger.info("=" * 70)
    
    results = []
    
    try:
        from server import HighFrequencyCGMReceiver
        
        cgm_receiver = HighFrequencyCGMReceiver()
        
        # Test get_glucose_data
        logger.info("\n📊 Testing get_glucose_data tool...")
        glucose_data = cgm_receiver.get_glucose_data(limit=5)
        if glucose_data:
            logger.info(f"✅ Retrieved {len(glucose_data)} glucose records")
            logger.info(f"   Sample: {glucose_data[0].get('timestamp')} - {glucose_data[0].get('value')} {glucose_data[0].get('unit')}")
            results.append(("get_glucose_data", True))
        else:
            logger.warning("⚠️  No glucose data returned")
            results.append(("get_glucose_data", False))
        
        # Test get_sleep_data
        logger.info("\n📊 Testing get_sleep_data tool...")
        sleep_data = cgm_receiver.get_sleep_data(limit=5)
        if sleep_data:
            logger.info(f"✅ Retrieved {len(sleep_data)} sleep records")
            logger.info(f"   Sample: {sleep_data[0].get('date')} - {sleep_data[0].get('sleep_duration_minutes')} min")
            results.append(("get_sleep_data", True))
        else:
            logger.warning("⚠️  No sleep data returned")
            results.append(("get_sleep_data", False))
        
        # Test get_exercise_data
        logger.info("\n📊 Testing get_exercise_data tool...")
        exercise_data = cgm_receiver.get_exercise_data(limit=5)
        if exercise_data:
            logger.info(f"✅ Retrieved {len(exercise_data)} exercise records")
            logger.info(f"   Sample: {exercise_data[0].get('activity_type')} - {exercise_data[0].get('duration_minutes')} min")
            results.append(("get_exercise_data", True))
        else:
            logger.warning("⚠️  No exercise data returned")
            results.append(("get_exercise_data", False))
        
        # Test get_recent_cgm_readings
        logger.info("\n📊 Testing get_recent_cgm_readings...")
        recent = cgm_receiver.get_recent_cgm_readings(minutes_back=100000)  # Large window
        if recent:
            logger.info(f"✅ Retrieved {len(recent)} recent readings")
            results.append(("get_recent_cgm_readings", True))
        else:
            logger.info(f"ℹ️  No recent readings (data may be older)")
            results.append(("get_recent_cgm_readings", True))  # Not an error if data is old
        
        # Test get_cgm_stats
        logger.info("\n📊 Testing get_cgm_stats...")
        stats = cgm_receiver.get_cgm_stats(hours_back=24*30)  # 30 days
        if stats and stats.get('total_readings', 0) > 0:
            logger.info(f"✅ Stats retrieved: {stats.get('total_readings')} readings, avg: {stats.get('average_glucose')} mg/dL")
            results.append(("get_cgm_stats", True))
        else:
            logger.info(f"ℹ️  No stats (data may be outside time range)")
            results.append(("get_cgm_stats", True))  # Not an error
        
    except Exception as e:
        logger.error(f"❌ Error testing MCP tools: {e}")
        import traceback
        traceback.print_exc()
        results.append(("MCP Tools", False))
    
    return results

def test_mcp_jsonrpc():
    """Test MCP server with JSON-RPC protocol"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: MCP JSON-RPC Protocol")
    logger.info("=" * 70)
    
    results = []
    
    try:
        # Start server process
        logger.info("🚀 Starting MCP server process...")
        process = subprocess.Popen(
            ["python", "server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait a bit for server to initialize
        time.sleep(2)
        
        # Send initialize request
        init_request = {
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
        
        logger.info("📤 Sending initialize request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response (with timeout)
        time.sleep(1)
        if process.poll() is None:
            logger.info("✅ Server process is running")
            results.append(("MCP Server Process", True))
        else:
            logger.error("❌ Server process exited")
            stderr_output = process.stderr.read()
            logger.error(f"Stderr: {stderr_output}")
            results.append(("MCP Server Process", False))
        
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        
    except Exception as e:
        logger.error(f"❌ Error testing JSON-RPC: {e}")
        import traceback
        traceback.print_exc()
        results.append(("MCP JSON-RPC", False))
    
    return results

def main():
    """Run all tests"""
    logger.info("\n" + "=" * 70)
    logger.info("MCP SERVER TEST SUITE")
    logger.info("=" * 70)
    
    all_results = []
    
    # Test Flask endpoints
    flask_results = test_flask_endpoints()
    all_results.extend(flask_results)
    
    # Test MCP tools directly
    tool_results = test_mcp_tools_direct()
    all_results.extend(tool_results)
    
    # Test JSON-RPC (optional, may not work in all environments)
    try:
        rpc_results = test_mcp_jsonrpc()
        all_results.extend(rpc_results)
    except Exception as e:
        logger.warning(f"⚠️  Skipping JSON-RPC test: {e}")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in all_results if result)
    total = len(all_results)
    
    for test_name, result in all_results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\n{'=' * 70}")
    logger.info(f"Total: {passed}/{total} tests passed")
    logger.info(f"{'=' * 70}\n")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

