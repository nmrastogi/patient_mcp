"""
SQLAlchemy models for RDS MySQL tables
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Text, 
    Index, UniqueConstraint, TIMESTAMP
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Glucose(Base):
    """Glucose/CGM readings table"""
    __tablename__ = 'glucose'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(255), nullable=False, index=True)
    glucose_mg_dl = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    hour = Column(Integer)
    minute = Column(Integer)
    source_name = Column(String(255))
    automation_type = Column(String(255))
    session_id = Column(String(255))
    raw_data = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('patient_id', 'timestamp', name='unique_patient_timestamp'),
        Index('idx_glucose_timestamp', 'patient_id', 'timestamp'),
        Index('idx_glucose_date_hour', 'patient_id', 'date', 'hour'),
        Index('idx_glucose_date', 'date'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'glucose_mg_dl': float(self.glucose_mg_dl) if self.glucose_mg_dl else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'date': str(self.date) if self.date else None,
            'hour': self.hour,
            'minute': self.minute,
            'source_name': self.source_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Sleep(Base):
    """Sleep data table"""
    __tablename__ = 'sleep'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(255), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    duration_hours = Column(Float)
    sleep_stage = Column(String(50))
    date = Column(Date, nullable=False, index=True)
    source_name = Column(String(255))
    automation_type = Column(String(255))
    session_id = Column(String(255))
    raw_data = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('patient_id', 'start_time', name='unique_patient_sleep_start'),
        Index('idx_sleep_timestamp', 'patient_id', 'start_time'),
        Index('idx_sleep_date', 'date'),
        Index('idx_sleep_patient_date', 'patient_id', 'date'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_hours': float(self.duration_hours) if self.duration_hours else None,
            'sleep_stage': self.sleep_stage,
            'date': str(self.date) if self.date else None,
            'source_name': self.source_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Exercise(Base):
    """Exercise/workout data table"""
    __tablename__ = 'exercise'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(255), nullable=False, index=True)
    workout_type = Column(String(255), index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    duration_minutes = Column(Float)
    total_distance = Column(Float)
    distance_unit = Column(String(50))
    total_energy = Column(Float)
    energy_unit = Column(String(50))
    date = Column(Date, nullable=False, index=True)
    source_name = Column(String(255))
    automation_type = Column(String(255))
    session_id = Column(String(255))
    raw_data = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('patient_id', 'workout_type', 'start_time', name='unique_patient_exercise_start'),
        Index('idx_exercise_timestamp', 'patient_id', 'start_time'),
        Index('idx_exercise_date', 'date'),
        Index('idx_exercise_type', 'workout_type'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'workout_type': self.workout_type,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': float(self.duration_minutes) if self.duration_minutes else None,
            'total_distance': float(self.total_distance) if self.total_distance else None,
            'distance_unit': self.distance_unit,
            'total_energy': float(self.total_energy) if self.total_energy else None,
            'energy_unit': self.energy_unit,
            'date': str(self.date) if self.date else None,
            'source_name': self.source_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


