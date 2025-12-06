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
    logger.info("=" * 70)
    logger.info("Testing RDS MySQL Tables: glucose, sleep, exercise")
    logger.info("=" * 70)
    
    receiver = HighFrequencyCGMReceiver()
    patient_id = "cgm_patient"
    
    # Calculate date range (last 30 days)
    end_date = datetime.now().date()
    start_date = (end_date - timedelta(days=30))
    
    logger.info(f"\n📊 Testing with patient_id: {patient_id}")
    logger.info(f"📅 Date range: {start_date} to {end_date}")
    logger.info("\n" + "-" * 70)
    
    # Test Glucose Table
    logger.info("\n1️⃣  GLUCOSE TABLE")
    logger.info("-" * 70)
    try:
        glucose_data = receiver.get_glucose_data(
            patient_id=patient_id,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=10
        )
        logger.info(f"✅ Retrieved {len(glucose_data)} glucose records")
        if glucose_data:
            logger.info(f"   Sample record:")
            sample = glucose_data[0]
            logger.info(f"   - Timestamp: {sample.get('timestamp')}")
            logger.info(f"   - Glucose: {sample.get('glucose_mg_dl')} mg/dL")
            logger.info(f"   - Source: {sample.get('source_name')}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    # Test Sleep Table
    logger.info("\n2️⃣  SLEEP TABLE")
    logger.info("-" * 70)
    try:
        sleep_data = receiver.get_sleep_data(
            patient_id=patient_id,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=10
        )
        logger.info(f"✅ Retrieved {len(sleep_data)} sleep records")
        if sleep_data:
            logger.info(f"   Sample record:")
            sample = sleep_data[0]
            logger.info(f"   - Start: {sample.get('start_time')}")
            logger.info(f"   - End: {sample.get('end_time')}")
            logger.info(f"   - Duration: {sample.get('duration_hours')} hours")
            logger.info(f"   - Stage: {sample.get('sleep_stage')}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    # Test Exercise Table
    logger.info("\n3️⃣  EXERCISE TABLE")
    logger.info("-" * 70)
    try:
        exercise_data = receiver.get_exercise_data(
            patient_id=patient_id,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=10
        )
        logger.info(f"✅ Retrieved {len(exercise_data)} exercise records")
        if exercise_data:
            logger.info(f"   Sample record:")
            sample = exercise_data[0]
            logger.info(f"   - Type: {sample.get('workout_type')}")
            logger.info(f"   - Start: {sample.get('start_time')}")
            logger.info(f"   - Duration: {sample.get('duration_minutes')} minutes")
            logger.info(f"   - Distance: {sample.get('total_distance')} {sample.get('distance_unit')}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ Test complete!")
    logger.info("=" * 70)
    
    # Summary
    logger.info("\n📋 Summary:")
    logger.info(f"   Glucose records: {len(glucose_data) if 'glucose_data' in locals() else 0}")
    logger.info(f"   Sleep records: {len(sleep_data) if 'sleep_data' in locals() else 0}")
    logger.info(f"   Exercise records: {len(exercise_data) if 'exercise_data' in locals() else 0}")

if __name__ == "__main__":
    try:
        test_all_tables()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

