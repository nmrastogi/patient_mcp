"""
SQLAlchemy models for RDS MySQL tables
Matching the actual RDS schema: sleep_data, exercise_data, blood_glucose
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Text, 
    Index, UniqueConstraint, TIMESTAMP, DECIMAL
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class BloodGlucose(Base):
    """Blood glucose/CGM readings table - matches RDS schema"""
    __tablename__ = 'blood_glucose'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    value = Column(DECIMAL(6, 2), nullable=False)  # glucose value in mg/dL
    unit = Column(String(10))
    source = Column(String(100))
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'value': float(self.value) if self.value else None,
            'glucose_mg_dl': float(self.value) if self.value else None,  # Alias for compatibility
            'unit': self.unit,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SleepData(Base):
    """Sleep data table - matches RDS schema"""
    __tablename__ = 'sleep_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    bedtime = Column(DateTime, nullable=False)
    wake_time = Column(DateTime, nullable=False)
    sleep_duration_minutes = Column(Integer)
    deep_sleep_minutes = Column(Integer)
    light_sleep_minutes = Column(Integer)
    rem_sleep_minutes = Column(Integer)
    sleep_efficiency = Column(DECIMAL(5, 2))
    heart_rate_avg = Column(Integer)
    heart_rate_min = Column(Integer)
    heart_rate_max = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'date': str(self.date) if self.date else None,
            'bedtime': self.bedtime.isoformat() if self.bedtime else None,
            'wake_time': self.wake_time.isoformat() if self.wake_time else None,
            'sleep_duration_minutes': self.sleep_duration_minutes,
            'deep_sleep_minutes': self.deep_sleep_minutes,
            'light_sleep_minutes': self.light_sleep_minutes,
            'rem_sleep_minutes': self.rem_sleep_minutes,
            'sleep_efficiency': float(self.sleep_efficiency) if self.sleep_efficiency else None,
            'heart_rate_avg': self.heart_rate_avg,
            'heart_rate_min': self.heart_rate_min,
            'heart_rate_max': self.heart_rate_max,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Compatibility fields
            'start_time': self.bedtime.isoformat() if self.bedtime else None,
            'end_time': self.wake_time.isoformat() if self.wake_time else None,
            'duration_hours': float(self.sleep_duration_minutes) / 60.0 if self.sleep_duration_minutes else None,
            'sleep_stage': 'asleep',  # Default since not in schema
        }


class ExerciseData(Base):
    """Exercise/workout data table - matches RDS schema (simplified)"""
    __tablename__ = 'exercise_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True, unique=True)
    duration_minutes = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'duration_minutes': self.duration_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Compatibility fields for backward compatibility
            'start_time': self.timestamp.isoformat() if self.timestamp else None,
            'date': self.timestamp.date().isoformat() if self.timestamp else None,
            'duration_hours': float(self.duration_minutes) / 60.0 if self.duration_minutes else None,
        }

# Create aliases for backward compatibility
Glucose = BloodGlucose
Sleep = SleepData
Exercise = ExerciseData
