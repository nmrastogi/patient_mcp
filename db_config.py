"""
Database configuration for Amazon RDS MySQL
"""
import os
import pymysql
from typing import Optional
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Configuration for RDS MySQL database connection"""
    
    def __init__(self):
        # RDS MySQL connection parameters from environment variables
        self.host = os.getenv('RDS_HOST', 'localhost')
        self.port = int(os.getenv('RDS_PORT', '3306'))
        self.user = os.getenv('RDS_USER', 'admin')
        self.password = os.getenv('RDS_PASSWORD', '')
        self.database = os.getenv('RDS_DATABASE', 'diabetes_cgm')
        self.charset = 'utf8mb4'
        self.connect_timeout = 10
        self.read_timeout = 30
        self.write_timeout = 30
        
        # Log configuration (without password)
        logger.info(f"Database config loaded: host={self.host}, port={self.port}, user={self.user}, database={self.database}")
        if not self.password:
            logger.warning("⚠️  RDS_PASSWORD not set - connection may fail")
        
    def get_connection(self):
        """Create a new MySQL connection"""
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                connect_timeout=self.connect_timeout,
                read_timeout=self.read_timeout,
                write_timeout=self.write_timeout,
                cursorclass=pymysql.cursors.DictCursor
            )
            return connection
        except Exception as e:
            logger.error(f"Failed to connect to MySQL database: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            conn.close()
            logger.info("✅ Successfully connected to MySQL database")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False

# Global database config instance
db_config = DatabaseConfig()

