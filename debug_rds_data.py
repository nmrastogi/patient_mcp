#!/usr/bin/env python3
"""
Debug script to check what data exists in RDS tables using SQLAlchemy
"""
import sys
import logging
from db_config import db_config
from models import Glucose, Sleep, Exercise
from sqlalchemy import func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_table_data():
    """Check what data exists in each table"""
    logger.info("=" * 70)
    logger.info("Debugging RDS Data - Checking Table Contents")
    logger.info("=" * 70)
    
    session = None
    try:
        session = db_config.get_session()
        
        # Check glucose table
        logger.info("\n📊 GLUCOSE TABLE:")
        logger.info("-" * 70)
        
        # Count total records
        total_glucose = session.query(func.count(Glucose.id)).scalar()
        logger.info(f"Total records: {total_glucose}")
        
        # Get unique patient_ids
        patient_ids = session.query(Glucose.patient_id).distinct().limit(10).all()
        logger.info(f"Unique patient_ids: {[p[0] for p in patient_ids]}")
        
        # Get date range
        date_range = session.query(
            func.min(Glucose.date).label('min_date'),
            func.max(Glucose.date).label('max_date')
        ).first()
        if date_range and date_range.min_date:
            logger.info(f"Date range: {date_range.min_date} to {date_range.max_date}")
        else:
            logger.info("No date data found")
        
        # Show sample records
        samples = session.query(Glucose).order_by(Glucose.timestamp.desc()).limit(3).all()
        if samples:
            logger.info(f"Sample records (last 3):")
            for i, sample in enumerate(samples, 1):
                logger.info(f"  {i}. Patient: {sample.patient_id}, "
                          f"Glucose: {sample.glucose_mg_dl}, "
                          f"Date: {sample.date}, "
                          f"Timestamp: {sample.timestamp}")
        else:
            logger.info("No sample records found")
        
        # Check sleep table
        logger.info("\n😴 SLEEP TABLE:")
        logger.info("-" * 70)
        
        total_sleep = session.query(func.count(Sleep.id)).scalar()
        logger.info(f"Total records: {total_sleep}")
        
        if total_sleep > 0:
            patient_ids = session.query(Sleep.patient_id).distinct().limit(10).all()
            logger.info(f"Unique patient_ids: {[p[0] for p in patient_ids]}")
            
            date_range = session.query(
                func.min(Sleep.date).label('min_date'),
                func.max(Sleep.date).label('max_date')
            ).first()
            if date_range and date_range.min_date:
                logger.info(f"Date range: {date_range.min_date} to {date_range.max_date}")
        
        # Check exercise table
        logger.info("\n🏃 EXERCISE TABLE:")
        logger.info("-" * 70)
        
        total_exercise = session.query(func.count(Exercise.id)).scalar()
        logger.info(f"Total records: {total_exercise}")
        
        if total_exercise > 0:
            patient_ids = session.query(Exercise.patient_id).distinct().limit(10).all()
            logger.info(f"Unique patient_ids: {[p[0] for p in patient_ids]}")
            
            date_range = session.query(
                func.min(Exercise.date).label('min_date'),
                func.max(Exercise.date).label('max_date')
            ).first()
            if date_range and date_range.min_date:
                logger.info(f"Date range: {date_range.min_date} to {date_range.max_date}")
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📋 SUMMARY:")
        logger.info(f"   Glucose records: {total_glucose}")
        logger.info(f"   Sleep records: {total_sleep}")
        logger.info(f"   Exercise records: {total_exercise}")
        
        if total_glucose == 0 and total_sleep == 0 and total_exercise == 0:
            logger.warning("\n⚠️  All tables are empty!")
            logger.info("This means:")
            logger.info("  1. No data has been inserted yet, OR")
            logger.info("  2. Data was inserted with different patient_id, OR")
            logger.info("  3. Data insertion failed silently")
            logger.info("\nTo insert data:")
            logger.info("  - Use the /health-data endpoint to receive data")
            logger.info("  - Or manually insert test data")
        else:
            logger.info("\n✅ Data exists in tables!")
            logger.info("If queries return 0, check:")
            logger.info("  - patient_id matches (case-sensitive)")
            logger.info("  - date range includes the data")
        
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Error checking data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    try:
        check_table_data()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

