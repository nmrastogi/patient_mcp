"""
Database configuration for Amazon RDS MySQL using SQLAlchemy
"""
import os
from typing import Optional
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Configuration for RDS MySQL database connection using SQLAlchemy"""
    
    def __init__(self):
        # RDS MySQL connection parameters from environment variables
        self.host = os.getenv('RDS_HOST', 'localhost')
        self.port = int(os.getenv('RDS_PORT', '3306'))
        self.user = os.getenv('RDS_USER', 'admin')
        self.password = os.getenv('RDS_PASSWORD', '')
        self.database = os.getenv('RDS_DATABASE', 'diabetes_cgm')
        self.charset = 'utf8mb4'
        
        # Log configuration (without password)
        logger.info(f"Database config loaded: host={self.host}, port={self.port}, user={self.user}, database={self.database}")
        if not self.password:
            logger.warning("⚠️  RDS_PASSWORD not set - connection may fail")
        
        # Create SQLAlchemy connection URL
        self.connection_url = (
            f"mysql+pymysql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?"
            f"charset={self.charset}"
        )
        
        # Create SQLAlchemy engine with connection pooling
        self.engine = create_engine(
            self.connection_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL query logging
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def get_connection(self):
        """Get raw connection (for backward compatibility)"""
        return self.engine.raw_connection()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Successfully connected to MySQL database")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False
    
    def create_tables(self):
        """Create all tables using SQLAlchemy"""
        from models import Base
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Database tables created/verified using SQLAlchemy")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating tables: {e}")
            return False

# Global database config instance
db_config = DatabaseConfig()

