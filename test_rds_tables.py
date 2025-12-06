#!/usr/bin/env python3
"""
Test script to retrieve data from all 3 RDS tables: glucose, sleep, and exercise
"""
import sys
import logging
from server import HighFrequencyCGMReceiver
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_all_tables():
    """Test retrieving data from all three tables"""
    print("=" * 70)
    print("Testing RDS MySQL Tables: glucose, sleep, exercise")
    print("=" * 70)
    
    receiver = HighFrequencyCGMReceiver()
    patient_id = "cgm_patient"
    
    # Calculate date range (last 30 days)
    end_date = datetime.now().date()
    start_date = (end_date - timedelta(days=30))
    
    print(f"\n📊 Testing with patient_id: {patient_id}")
    print(f"📅 Date range: {start_date} to {end_date}")
    print("\n" + "-" * 70)
    
    # Test Glucose Table
    print("\n1️⃣  GLUCOSE TABLE")
    print("-" * 70)
    try:
        glucose_data = receiver.get_glucose_data(
            patient_id=patient_id,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=10
        )
        print(f"✅ Retrieved {len(glucose_data)} glucose records")
        if glucose_data:
            print(f"   Sample record:")
            sample = glucose_data[0]
            print(f"   - Timestamp: {sample.get('timestamp')}")
            print(f"   - Glucose: {sample.get('glucose_mg_dl')} mg/dL")
            print(f"   - Source: {sample.get('source_name')}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test Sleep Table
    print("\n2️⃣  SLEEP TABLE")
    print("-" * 70)
    try:
        sleep_data = receiver.get_sleep_data(
            patient_id=patient_id,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=10
        )
        print(f"✅ Retrieved {len(sleep_data)} sleep records")
        if sleep_data:
            print(f"   Sample record:")
            sample = sleep_data[0]
            print(f"   - Start: {sample.get('start_time')}")
            print(f"   - End: {sample.get('end_time')}")
            print(f"   - Duration: {sample.get('duration_hours')} hours")
            print(f"   - Stage: {sample.get('sleep_stage')}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test Exercise Table
    print("\n3️⃣  EXERCISE TABLE")
    print("-" * 70)
    try:
        exercise_data = receiver.get_exercise_data(
            patient_id=patient_id,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=10
        )
        print(f"✅ Retrieved {len(exercise_data)} exercise records")
        if exercise_data:
            print(f"   Sample record:")
            sample = exercise_data[0]
            print(f"   - Type: {sample.get('workout_type')}")
            print(f"   - Start: {sample.get('start_time')}")
            print(f"   - Duration: {sample.get('duration_minutes')} minutes")
            print(f"   - Distance: {sample.get('total_distance')} {sample.get('distance_unit')}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Test complete!")
    print("=" * 70)
    
    # Summary
    print("\n📋 Summary:")
    print(f"   Glucose records: {len(glucose_data) if 'glucose_data' in locals() else 0}")
    print(f"   Sleep records: {len(sleep_data) if 'sleep_data' in locals() else 0}")
    print(f"   Exercise records: {len(exercise_data) if 'exercise_data' in locals() else 0}")

if __name__ == "__main__":
    try:
        test_all_tables()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

