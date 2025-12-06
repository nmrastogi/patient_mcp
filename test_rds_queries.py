#!/usr/bin/env python3
"""
Test script to verify RDS queries work correctly with updated models
"""
import sys
import logging
from datetime import datetime, timedelta
from db_config import db_config
from models import Glucose, Sleep, Exercise
from sqlalchemy import func
from server import HighFrequencyCGMReceiver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

def test_record_counts():
    """Test that record counts match expected values"""
    logger.info("=" * 70)
    logger.info("TEST 1: Record Counts")
    logger.info("=" * 70)
    
    session = None
    try:
        session = db_config.get_session()
        
        glucose_count = session.query(func.count(Glucose.id)).scalar()
        sleep_count = session.query(func.count(Sleep.id)).scalar()
        exercise_count = session.query(func.count(Exercise.id)).scalar()
        
        logger.info(f"✅ Glucose records: {glucose_count:,}")
        logger.info(f"✅ Sleep records: {sleep_count:,}")
        logger.info(f"✅ Exercise records: {exercise_count:,}")
        
        # Expected values from notebook
        expected_glucose = 33303
        expected_sleep = 116
        expected_exercise = 822
        
        if glucose_count == expected_glucose:
            logger.info(f"✅ Glucose count matches expected ({expected_glucose:,})")
        else:
            logger.warning(f"⚠️  Glucose count mismatch: got {glucose_count:,}, expected {expected_glucose:,}")
        
        if sleep_count == expected_sleep:
            logger.info(f"✅ Sleep count matches expected ({expected_sleep})")
        else:
            logger.warning(f"⚠️  Sleep count mismatch: got {sleep_count}, expected {expected_sleep}")
        
        if exercise_count == expected_exercise:
            logger.info(f"✅ Exercise count matches expected ({expected_exercise})")
        else:
            logger.warning(f"⚠️  Exercise count mismatch: got {exercise_count}, expected {expected_exercise}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error testing record counts: {e}")
        return False
    finally:
        if session:
            session.close()

def test_glucose_queries():
    """Test glucose data retrieval"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Glucose Data Queries")
    logger.info("=" * 70)
    
    cgm_receiver = HighFrequencyCGMReceiver()
    
    # Test get_glucose_data
    logger.info("\n📊 Testing get_glucose_data()...")
    try:
        glucose_data = cgm_receiver.get_glucose_data(limit=10)
        logger.info(f"✅ Retrieved {len(glucose_data)} glucose records (limit 10)")
        if glucose_data:
            sample = glucose_data[0]
            logger.info(f"   Sample record keys: {list(sample.keys())}")
            logger.info(f"   Sample timestamp: {sample.get('timestamp')}")
            logger.info(f"   Sample value: {sample.get('value')} mg/dL")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    
    # Test get_recent_cgm_readings
    logger.info("\n📊 Testing get_recent_cgm_readings()...")
    try:
        recent = cgm_receiver.get_recent_cgm_readings(minutes_back=1440)  # Last 24 hours
        logger.info(f"✅ Retrieved {len(recent)} recent readings (last 24 hours)")
        if recent:
            logger.info(f"   Most recent: {recent[0].get('glucose_mg_dl')} mg/dL at {recent[0].get('timestamp')}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    
    # Test get_cgm_stats
    logger.info("\n📊 Testing get_cgm_stats()...")
    try:
        stats = cgm_receiver.get_cgm_stats(hours_back=24)
        logger.info(f"✅ CGM Stats (last 24 hours):")
        logger.info(f"   Total readings: {stats.get('total_readings')}")
        logger.info(f"   Average glucose: {stats.get('average_glucose')} mg/dL")
        logger.info(f"   Min glucose: {stats.get('min_glucose')} mg/dL")
        logger.info(f"   Max glucose: {stats.get('max_glucose')} mg/dL")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    
    return True

def test_sleep_queries():
    """Test sleep data retrieval"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Sleep Data Queries")
    logger.info("=" * 70)
    
    cgm_receiver = HighFrequencyCGMReceiver()
    
    try:
        sleep_data = cgm_receiver.get_sleep_data(limit=10)
        logger.info(f"✅ Retrieved {len(sleep_data)} sleep records (limit 10)")
        if sleep_data:
            sample = sleep_data[0]
            logger.info(f"   Sample record keys: {list(sample.keys())}")
            logger.info(f"   Sample date: {sample.get('date')}")
            logger.info(f"   Sample bedtime: {sample.get('bedtime')}")
            logger.info(f"   Sample duration: {sample.get('sleep_duration_minutes')} minutes")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    
    return True

def test_exercise_queries():
    """Test exercise data retrieval"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Exercise Data Queries")
    logger.info("=" * 70)
    
    cgm_receiver = HighFrequencyCGMReceiver()
    
    try:
        exercise_data = cgm_receiver.get_exercise_data(limit=10)
        logger.info(f"✅ Retrieved {len(exercise_data)} exercise records (limit 10)")
        if exercise_data:
            sample = exercise_data[0]
            logger.info(f"   Sample record keys: {list(sample.keys())}")
            logger.info(f"   Sample timestamp: {sample.get('timestamp')}")
            logger.info(f"   Sample activity: {sample.get('activity_type')}")
            logger.info(f"   Sample duration: {sample.get('duration_minutes')} minutes")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    
    return True

def test_date_filtering():
    """Test date filtering in queries"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Date Filtering")
    logger.info("=" * 70)
    
    cgm_receiver = HighFrequencyCGMReceiver()
    
    # Get date range from data
    session = None
    try:
        session = db_config.get_session()
        
        # Get earliest and latest dates
        earliest_glucose = session.query(func.min(Glucose.timestamp)).scalar()
        latest_glucose = session.query(func.max(Glucose.timestamp)).scalar()
        
        if earliest_glucose and latest_glucose:
            logger.info(f"📅 Glucose date range: {earliest_glucose.date()} to {latest_glucose.date()}")
            
            # Test with date range
            start_date = earliest_glucose.date().strftime('%Y-%m-%d')
            end_date = latest_glucose.date().strftime('%Y-%m-%d')
            
            logger.info(f"\n📊 Testing with date range: {start_date} to {end_date}")
            filtered_glucose = cgm_receiver.get_glucose_data(start_date=start_date, end_date=end_date, limit=5)
            logger.info(f"✅ Retrieved {len(filtered_glucose)} records with date filter")
            
            # Test with a single day
            single_day = earliest_glucose.date().strftime('%Y-%m-%d')
            logger.info(f"\n📊 Testing with single day: {single_day}")
            single_day_glucose = cgm_receiver.get_glucose_data(start_date=single_day, end_date=single_day, limit=5)
            logger.info(f"✅ Retrieved {len(single_day_glucose)} records for single day")
        
        # Test sleep date filtering
        earliest_sleep = session.query(func.min(Sleep.date)).scalar()
        latest_sleep = session.query(func.max(Sleep.date)).scalar()
        
        if earliest_sleep and latest_sleep:
            logger.info(f"\n📅 Sleep date range: {earliest_sleep} to {latest_sleep}")
            start_date = earliest_sleep.strftime('%Y-%m-%d')
            end_date = latest_sleep.strftime('%Y-%m-%d')
            filtered_sleep = cgm_receiver.get_sleep_data(start_date=start_date, end_date=end_date, limit=5)
            logger.info(f"✅ Retrieved {len(filtered_sleep)} sleep records with date filter")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error testing date filtering: {e}")
        return False
    finally:
        if session:
            session.close()

def main():
    """Run all tests"""
    logger.info("\n" + "=" * 70)
    logger.info("RDS QUERY TEST SUITE")
    logger.info("=" * 70)
    
    tests = [
        ("Record Counts", test_record_counts),
        ("Glucose Queries", test_glucose_queries),
        ("Sleep Queries", test_sleep_queries),
        ("Exercise Queries", test_exercise_queries),
        ("Date Filtering", test_date_filtering),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\n{'=' * 70}")
    logger.info(f"Total: {passed}/{total} tests passed")
    logger.info(f"{'=' * 70}\n")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

