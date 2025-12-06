#!/usr/bin/env python3
"""
Simplified MCP Server for Diabetes Data
Provides 3 tools to retrieve data from RDS MySQL:
- get_glucose_data
- get_sleep_data
- get_exercise_data
"""
from mcp.server.fastmcp import FastMCP
from db_config import db_config
from models import Glucose, Sleep, Exercise
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import sys

# Configure logging to stderr (MCP uses stdout for JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP(name="DiabetesDataServer")

@mcp.tool()
def get_glucose_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000
) -> Dict:
    """
    Get glucose/blood glucose data from RDS MySQL database.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (default: 1000)
    
    Returns:
        Dictionary with total_records, date_range, and data array
    """
    session = None
    try:
        session = db_config.get_session()
        
        query = session.query(Glucose)
        
        # Apply date filters if provided
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(Glucose.timestamp >= start_dt, Glucose.timestamp < end_dt)
            except ValueError as e:
                return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD"}
        
        # Get results
        results = query.order_by(Glucose.timestamp.desc()).limit(limit).all()
        data = [record.to_dict() for record in results]
        
        return {
            "table": "blood_glucose",
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting glucose data: {e}")
        return {"error": str(e), "table": "blood_glucose"}
    finally:
        if session:
            session.close()

@mcp.tool()
def get_sleep_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000
) -> Dict:
    """
    Get sleep data from RDS MySQL database.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (default: 1000)
    
    Returns:
        Dictionary with total_records, date_range, and data array
    """
    session = None
    try:
        session = db_config.get_session()
        
        query = session.query(Sleep)
        
        # Apply date filters if provided
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Sleep.date >= start_dt, Sleep.date <= end_dt)
            except ValueError as e:
                return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD"}
        
        # Get results
        results = query.order_by(Sleep.bedtime.desc()).limit(limit).all()
        data = [record.to_dict() for record in results]
        
        return {
            "table": "sleep_data",
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting sleep data: {e}")
        return {"error": str(e), "table": "sleep_data"}
    finally:
        if session:
            session.close()

@mcp.tool()
def get_exercise_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000
) -> Dict:
    """
    Get exercise/workout data from RDS MySQL database.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (default: 1000)
    
    Returns:
        Dictionary with total_records, date_range, and data array
    """
    session = None
    try:
        session = db_config.get_session()
        
        query = session.query(Exercise)
        
        # Apply date filters if provided
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(Exercise.timestamp >= start_dt, Exercise.timestamp < end_dt)
            except ValueError as e:
                return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD"}
        
        # Get results
        results = query.order_by(Exercise.timestamp.desc()).limit(limit).all()
        data = [record.to_dict() for record in results]
        
        return {
            "table": "exercise_data",
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting exercise data: {e}")
        return {"error": str(e), "table": "exercise_data"}
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    # Initialize database connection
    try:
        from sqlalchemy import inspect
        inspector = inspect(db_config.engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"✅ Connected to RDS. Tables: {', '.join(existing_tables)}")
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
    
    logger.info("🚀 Starting Diabetes Data MCP Server...")
    logger.info("📊 Available tools: get_glucose_data, get_sleep_data, get_exercise_data")
    
    # Start MCP server (blocks and handles stdio communication)
    mcp.run(transport='stdio')

