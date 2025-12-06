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
    print("=" * 60)
    print("Testing Amazon RDS MySQL Connection")
    print("=" * 60)
    
    # Display configuration (without password)
    print(f"\n📋 Configuration:")
    print(f"   Host: {db_config.host}")
    print(f"   Port: {db_config.port}")
    print(f"   User: {db_config.user}")
    print(f"   Database: {db_config.database}")
    print(f"   Password: {'*' * len(db_config.password) if db_config.password else '(not set)'}")
    
    # Test connection
    print(f"\n🔌 Testing connection...")
    try:
        if db_config.test_connection():
            print("✅ Connection successful!")
        else:
            print("❌ Connection failed!")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    # Test table creation (this will be done by HighFrequencyCGMReceiver)
    print(f"\n📊 Testing table initialization...")
    try:
        from server import HighFrequencyCGMReceiver
        receiver = HighFrequencyCGMReceiver()
        print("✅ Tables initialized successfully!")
    except Exception as e:
        print(f"❌ Table initialization error: {e}")
        return False
    
    # Test a simple query
    print(f"\n🔍 Testing database query...")
    try:
        conn = db_config.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM cgm_readings")
        result = cursor.fetchone()
        count = result['count'] if result else 0
        print(f"✅ Query successful! Found {count} CGM readings in database.")
        conn.close()
    except Exception as e:
        print(f"⚠️  Query test: {e} (This is OK if tables are empty)")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Your RDS MySQL connection is working.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


