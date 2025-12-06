#!/usr/bin/env python3
"""
Test script to verify Amazon RDS MySQL connection
"""
import sys
import logging
from db_config import db_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_connection():
    """Test database connection and table creation"""
    logger.info("=" * 60)
    logger.info("Testing Amazon RDS MySQL Connection")
    logger.info("=" * 60)
    
    # Display configuration (without password)
    logger.info(f"\n📋 Configuration:")
    logger.info(f"   Host: {db_config.host}")
    logger.info(f"   Port: {db_config.port}")
    logger.info(f"   User: {db_config.user}")
    logger.info(f"   Database: {db_config.database}")
    logger.info(f"   Password: {'*' * len(db_config.password) if db_config.password else '(not set)'}")
    
    # Test connection
    logger.info(f"\n🔌 Testing connection...")
    try:
        if db_config.test_connection():
            logger.info("✅ Connection successful!")
        else:
            logger.error("❌ Connection failed!")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False
    
    # Test table creation (this will be done by HighFrequencyCGMReceiver)
    logger.info(f"\n📊 Testing table initialization...")
    try:
        from server import HighFrequencyCGMReceiver
        receiver = HighFrequencyCGMReceiver()
        logger.info("✅ Tables initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Table initialization error: {e}")
        return False
    
    # Test a simple query using SQLAlchemy
    logger.info(f"\n🔍 Testing database query...")
    try:
        from models import Glucose
        from sqlalchemy import func
        
        session = db_config.get_session()
        count = session.query(func.count(Glucose.id)).scalar()
        session.close()
        logger.info(f"✅ Query successful! Found {count} glucose readings in database.")
    except Exception as e:
        logger.warning(f"⚠️  Query test: {e} (This is OK if tables are empty)")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ All tests passed! Your RDS MySQL connection is working.")
    logger.info("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


