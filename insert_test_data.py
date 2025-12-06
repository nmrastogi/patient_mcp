#!/usr/bin/env python3
"""
Insert test data into RDS tables for testing using SQLAlchemy
"""
import sys
import logging
from db_config import db_config
from models import Glucose, Sleep, Exercise
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def insert_test_data():
    """Insert sample test data into all three tables using SQLAlchemy"""
    logger.info("=" * 70)
    logger.info("Inserting Test Data into RDS Tables (SQLAlchemy)")
    logger.info("=" * 70)
    
    session = None
    try:
        session = db_config.get_session()
        
        patient_id = "cgm_patient"
        base_time = datetime.now() - timedelta(days=7)
        
        # Insert test glucose data
        logger.info("\n📊 Inserting glucose test data...")
        glucose_inserted = 0
        for i in range(20):
            timestamp = base_time + timedelta(hours=i*3)
            glucose_value = 100 + (i % 20) * 5  # Vary between 100-195
            
            try:
                # Check if exists
                existing = session.query(Glucose).filter(
                    Glucose.patient_id == patient_id,
                    Glucose.timestamp == timestamp
                ).first()
                
                if not existing:
                    glucose_record = Glucose(
                        patient_id=patient_id,
                        glucose_mg_dl=glucose_value,
                        timestamp=timestamp,
                        date=timestamp.date(),
                        hour=timestamp.hour,
                        minute=timestamp.minute,
                        source_name="test_source"
                    )
                    session.add(glucose_record)
                    glucose_inserted += 1
            except Exception as e:
                logger.warning(f"Error inserting glucose record {i}: {e}")
        
        logger.info(f"✅ Inserted {glucose_inserted} glucose records")
        
        # Insert test sleep data
        logger.info("\n😴 Inserting sleep test data...")
        sleep_inserted = 0
        for i in range(5):
            start_time = base_time + timedelta(days=i, hours=22)
            end_time = start_time + timedelta(hours=8)
            
            try:
                existing = session.query(Sleep).filter(
                    Sleep.patient_id == patient_id,
                    Sleep.start_time == start_time
                ).first()
                
                if not existing:
                    sleep_record = Sleep(
                        patient_id=patient_id,
                        start_time=start_time,
                        end_time=end_time,
                        duration_hours=8.0,
                        sleep_stage="asleep",
                        date=start_time.date(),
                        source_name="test_source"
                    )
                    session.add(sleep_record)
                    sleep_inserted += 1
            except Exception as e:
                logger.warning(f"Error inserting sleep record {i}: {e}")
        
        logger.info(f"✅ Inserted {sleep_inserted} sleep records")
        
        # Insert test exercise data
        logger.info("\n🏃 Inserting exercise test data...")
        exercise_inserted = 0
        workout_types = ["Running", "Walking", "Cycling", "Swimming"]
        
        for i in range(8):
            start_time = base_time + timedelta(days=i, hours=8)
            end_time = start_time + timedelta(minutes=30 + i*5)
            
            try:
                existing = session.query(Exercise).filter(
                    Exercise.patient_id == patient_id,
                    Exercise.workout_type == workout_types[i % len(workout_types)],
                    Exercise.start_time == start_time
                ).first()
                
                if not existing:
                    exercise_record = Exercise(
                        patient_id=patient_id,
                        workout_type=workout_types[i % len(workout_types)],
                        start_time=start_time,
                        end_time=end_time,
                        duration_minutes=30 + i*5,
                        total_distance=2.5 + i*0.3,
                        distance_unit="miles",
                        total_energy=200 + i*20,
                        energy_unit="calories",
                        date=start_time.date(),
                        source_name="test_source"
                    )
                    session.add(exercise_record)
                    exercise_inserted += 1
            except Exception as e:
                logger.warning(f"Error inserting exercise record {i}: {e}")
        
        logger.info(f"✅ Inserted {exercise_inserted} exercise records")
        
        session.commit()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ Test data insertion complete!")
        logger.info(f"   Glucose: {glucose_inserted} records")
        logger.info(f"   Sleep: {sleep_inserted} records")
        logger.info(f"   Exercise: {exercise_inserted} records")
        logger.info("=" * 70)
        logger.info("\nYou can now test the MCP tools:")
        logger.info("  python test_rds_tables.py")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inserting test data: {e}")
        if session:
            session.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    try:
        success = insert_test_data()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

