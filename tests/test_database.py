"""
Pytest tests for database connection and models
"""
import pytest
from db_config import db_config
from models import Glucose, Sleep, Exercise
from sqlalchemy import func, inspect


class TestDatabaseConnection:
    """Test database connection and configuration"""
    
    def test_database_connection(self):
        """Test that database connection works"""
        assert db_config.test_connection() is True
    
    def test_database_tables_exist(self):
        """Test that all required tables exist"""
        inspector = inspect(db_config.engine)
        tables = inspector.get_table_names()
        
        assert 'blood_glucose' in tables
        assert 'sleep_data' in tables
        assert 'exercise_data' in tables
    
    def test_glucose_table_has_data(self):
        """Test that glucose table has records"""
        session = db_config.get_session()
        try:
            count = session.query(func.count(Glucose.id)).scalar()
            assert count > 0, "Glucose table should have records"
        finally:
            session.close()
    
    def test_sleep_table_has_data(self):
        """Test that sleep table has records"""
        session = db_config.get_session()
        try:
            count = session.query(func.count(Sleep.id)).scalar()
            assert count > 0, "Sleep table should have records"
        finally:
            session.close()
    
    def test_exercise_table_has_data(self):
        """Test that exercise table has records"""
        session = db_config.get_session()
        try:
            count = session.query(func.count(Exercise.id)).scalar()
            assert count > 0, "Exercise table should have records"
        finally:
            session.close()


class TestModels:
    """Test SQLAlchemy models"""
    
    def test_glucose_model(self):
        """Test Glucose model structure"""
        session = db_config.get_session()
        try:
            # Get one record
            record = session.query(Glucose).first()
            assert record is not None
            
            # Test to_dict method
            data = record.to_dict()
            assert 'id' in data
            assert 'timestamp' in data
            assert 'value' in data
            assert 'glucose_mg_dl' in data  # Compatibility field
        finally:
            session.close()
    
    def test_sleep_model(self):
        """Test Sleep model structure"""
        session = db_config.get_session()
        try:
            # Get one record
            record = session.query(Sleep).first()
            assert record is not None
            
            # Test to_dict method
            data = record.to_dict()
            assert 'id' in data
            assert 'date' in data
            assert 'bedtime' in data
            assert 'wake_time' in data
            assert 'sleep_duration_minutes' in data
        finally:
            session.close()
    
    def test_exercise_model(self):
        """Test Exercise model structure"""
        session = db_config.get_session()
        try:
            # Get one record
            record = session.query(Exercise).first()
            assert record is not None
            
            # Test to_dict method
            data = record.to_dict()
            assert 'id' in data
            assert 'timestamp' in data
            assert 'activity_type' in data
            assert 'duration_minutes' in data
        finally:
            session.close()


