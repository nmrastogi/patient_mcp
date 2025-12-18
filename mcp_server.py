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
from typing import Dict, List, Optional, Type, Any
from sqlalchemy.orm import Query
from sqlalchemy import Column
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


def _validate_date_params(start_date: Optional[str], end_date: Optional[str]) -> Optional[Dict]:
    """Validate date parameters and return error dict if invalid"""
    if start_date and not end_date:
        return {"error": "Both start_date and end_date must be provided together"}
    if end_date and not start_date:
        return {"error": "Both start_date and end_date must be provided together"}
    return None


def _validate_limit(limit: Optional[int]) -> Optional[Dict]:
    """Validate limit parameter"""
    if limit is not None and limit < 1:
        return {"error": "Limit must be greater than 0 or None (for all records)"}
    return None


def _parse_dates(start_date: str, end_date: str, use_date_field: bool = False) -> tuple[datetime, datetime] | Dict:
    """
    Parse date strings and return datetime objects or error dict.
    
    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        use_date_field: If True, return date objects instead of datetime
    
    Returns:
        Tuple of (start_dt, end_dt) or error dict
    """
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            return {"error": "start_date must be before or equal to end_date"}
        
        # For date fields, return date objects; for datetime fields, add 1 day to end
        if use_date_field:
            return (start_dt.date(), end_dt.date())
        else:
            return (start_dt, end_dt + timedelta(days=1))
    except ValueError as e:
        return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD format"}


def _apply_date_filter(
    query: Query,
    model_class: Type,
    start_date: Optional[str],
    end_date: Optional[str]
) -> tuple[Query, Optional[Dict]]:
    """
    Apply date filtering to query based on model type.
    
    Returns:
        Tuple of (filtered_query, error_dict_or_none)
    """
    if not (start_date and end_date):
        return query, None
    
    # Check if model uses 'date' field (Sleep) or 'timestamp' field (Glucose, Exercise)
    has_date_field = hasattr(model_class, 'date')
    has_timestamp_field = hasattr(model_class, 'timestamp')
    
    if not (has_date_field or has_timestamp_field):
        return query, {"error": f"Model {model_class.__name__} has no date or timestamp field"}
    
    # Parse dates
    date_result = _parse_dates(start_date, end_date, use_date_field=has_date_field)
    if isinstance(date_result, dict):  # Error dict
        return query, date_result
    
    start_dt, end_dt = date_result
    
    # Apply appropriate filter
    if has_date_field:
        query = query.filter(model_class.date >= start_dt, model_class.date <= end_dt)
    else:  # has_timestamp_field
        query = query.filter(model_class.timestamp >= start_dt, model_class.timestamp < end_dt)
    
    return query, None


def _get_data_generic(
    model_class: Type,
    table_name: str,
    order_by_field: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict:
    """
    Generic function to retrieve data from any table.
    
    Args:
        model_class: SQLAlchemy model class
        table_name: Name of the table (for response)
        order_by_field: Field name to order by (e.g., 'timestamp', 'bedtime')
        start_date: Start date filter (optional)
        end_date: End date filter (optional)
        limit: Maximum records to return (None = all records)
    
    Returns:
        Dictionary with table, total_records, date_range, and data
    """
    session = None
    try:
        # Validate inputs
        limit_error = _validate_limit(limit)
        if limit_error:
            return limit_error
        
        date_error = _validate_date_params(start_date, end_date)
        if date_error:
            return date_error
        
        # Get database session
        session = db_config.get_session()
        
        # Build query
        query = session.query(model_class)
        
        # Apply date filters
        query, date_error = _apply_date_filter(query, model_class, start_date, end_date)
        if date_error:
            return date_error
        
        # Get order by field
        order_field = getattr(model_class, order_by_field)
        if order_field is None:
            return {"error": f"Model {model_class.__name__} has no field '{order_by_field}'"}
        
        # Execute query with optional limit
        query = query.order_by(order_field.desc())
        if limit is not None:
            results = query.limit(limit).all()
        else:
            results = query.all()
        
        data = [record.to_dict() for record in results]
        
        return {
            "table": table_name,
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "limit": limit if limit is not None else "unlimited",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting {table_name} data: {e}", exc_info=True)
        return {"error": str(e), "table": table_name}
    finally:
        if session:
            session.close()


@mcp.tool()
def get_glucose_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict:
    """
    Get glucose/blood glucose data from RDS MySQL database.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (None = all records, default: None)
    
    Returns:
        Dictionary with total_records, date_range, limit, and data array
    """
    return _get_data_generic(
        model_class=Glucose,
        table_name="blood_glucose",
        order_by_field="timestamp",
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


@mcp.tool()
def get_sleep_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict:
    """
    Get sleep data from RDS MySQL database.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (None = all records, default: None)
    
    Returns:
        Dictionary with total_records, date_range, limit, and data array
    """
    return _get_data_generic(
        model_class=Sleep,
        table_name="sleep_data",
        order_by_field="bedtime",
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


@mcp.tool()
def get_exercise_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict:
    """
    Get exercise/workout data from RDS MySQL database.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        limit: Maximum number of records to return (None = all records, default: None)
    
    Returns:
        Dictionary with total_records, date_range, limit, and data array
    """
    return _get_data_generic(
        model_class=Exercise,
        table_name="exercise_data",
        order_by_field="timestamp",
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


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
