#!/usr/bin/env python3
"""
Simplified MCP Server for Diabetes Data
Provides 5 tools to retrieve and analyze data from RDS MySQL:
- get_glucose_data
- get_sleep_data
- get_exercise_data
- detect_patterns
- find_correlations
"""
from mcp.server.fastmcp import FastMCP
from db_config import db_config
from models import Glucose, Sleep, Exercise
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Type, Any
from sqlalchemy.orm import Query
from sqlalchemy import Column, func
from collections import defaultdict, Counter
from statistics import mean, stdev
import logging
import sys
import math

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


@mcp.tool()
def detect_patterns(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    pattern_type: Optional[str] = "all"
) -> Dict:
    """
    Detect patterns in diabetes data including time-based patterns, value patterns, and behavioral patterns.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        pattern_type: Type of patterns to detect - "all", "glucose", "sleep", "exercise", "temporal" (default: "all")
    
    Returns:
        Dictionary with detected patterns including:
        - glucose_patterns: Time-based glucose patterns (hourly, daily, weekly)
        - sleep_patterns: Sleep duration and timing patterns
        - exercise_patterns: Exercise frequency and timing patterns
        - temporal_patterns: Day-of-week and time-of-day patterns
    """
    session = None
    try:
        # Validate date parameters
        date_error = _validate_date_params(start_date, end_date)
        if date_error:
            return date_error
        
        session = db_config.get_session()
        patterns = {
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "pattern_type": pattern_type,
            "patterns": {}
        }
        
        # Apply date filters if provided
        glucose_query = session.query(Glucose)
        sleep_query = session.query(Sleep)
        exercise_query = session.query(Exercise)
        
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            
            glucose_query = glucose_query.filter(
                Glucose.timestamp >= start_dt,
                Glucose.timestamp < end_dt
            )
            sleep_query = sleep_query.filter(
                Sleep.date >= start_dt.date(),
                Sleep.date <= end_dt.date()
            )
            exercise_query = exercise_query.filter(
                Exercise.timestamp >= start_dt,
                Exercise.timestamp < end_dt
            )
        
        # Detect glucose patterns
        if pattern_type in ["all", "glucose", "temporal"]:
            glucose_records = glucose_query.all()
            if glucose_records:
                patterns["patterns"]["glucose"] = _detect_glucose_patterns(glucose_records)
        
        # Detect sleep patterns
        if pattern_type in ["all", "sleep", "temporal"]:
            sleep_records = sleep_query.all()
            if sleep_records:
                patterns["patterns"]["sleep"] = _detect_sleep_patterns(sleep_records)
        
        # Detect exercise patterns
        if pattern_type in ["all", "exercise", "temporal"]:
            exercise_records = exercise_query.all()
            if exercise_records:
                patterns["patterns"]["exercise"] = _detect_exercise_patterns(exercise_records)
        
        return patterns
        
    except Exception as e:
        logger.error(f"Error detecting patterns: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        if session:
            session.close()


def _detect_glucose_patterns(glucose_records: List) -> Dict:
    """Detect patterns in glucose data"""
    patterns = {
        "hourly_averages": {},
        "day_of_week_averages": {},
        "high_glucose_times": [],
        "low_glucose_times": [],
        "time_in_range_by_hour": {}
    }
    
    hourly_values = defaultdict(list)
    day_of_week_values = defaultdict(list)
    high_glucose_periods = []
    low_glucose_periods = []
    time_in_range_by_hour = defaultdict(lambda: {"in_range": 0, "total": 0})
    
    for record in glucose_records:
        if not record.value:
            continue
        
        value = float(record.value)
        timestamp = record.timestamp
        
        # Hourly patterns
        hour = timestamp.hour
        hourly_values[hour].append(value)
        
        # Day of week patterns
        day_name = timestamp.strftime("%A")
        day_of_week_values[day_name].append(value)
        
        # Time in range by hour (70-180 mg/dL)
        in_range = 70 <= value <= 180
        time_in_range_by_hour[hour]["total"] += 1
        if in_range:
            time_in_range_by_hour[hour]["in_range"] += 1
        
        # High glucose detection (>180 mg/dL)
        if value > 180:
            high_glucose_periods.append({
                "timestamp": timestamp.isoformat(),
                "value": value,
                "hour": hour
            })
        
        # Low glucose detection (<70 mg/dL)
        if value < 70:
            low_glucose_periods.append({
                "timestamp": timestamp.isoformat(),
                "value": value,
                "hour": hour
            })
    
    # Calculate hourly averages
    for hour in range(24):
        if hour in hourly_values:
            values = hourly_values[hour]
            patterns["hourly_averages"][hour] = {
                "average": round(mean(values), 2),
                "count": len(values),
                "min": round(min(values), 2),
                "max": round(max(values), 2)
            }
    
    # Calculate day of week averages
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        if day in day_of_week_values:
            values = day_of_week_values[day]
            patterns["day_of_week_averages"][day] = {
                "average": round(mean(values), 2),
                "count": len(values),
                "min": round(min(values), 2),
                "max": round(max(values), 2)
            }
    
    # Find most common high glucose times
    high_glucose_hours = Counter([p["hour"] for p in high_glucose_periods])
    patterns["high_glucose_times"] = [
        {"hour": hour, "count": count}
        for hour, count in high_glucose_hours.most_common(5)
    ]
    
    # Find most common low glucose times
    low_glucose_hours = Counter([p["hour"] for p in low_glucose_periods])
    patterns["low_glucose_times"] = [
        {"hour": hour, "count": count}
        for hour, count in low_glucose_hours.most_common(5)
    ]
    
    # Calculate time in range percentage by hour
    for hour in range(24):
        if hour in time_in_range_by_hour:
            data = time_in_range_by_hour[hour]
            if data["total"] > 0:
                patterns["time_in_range_by_hour"][hour] = {
                    "percentage": round((data["in_range"] / data["total"]) * 100, 2),
                    "total_readings": data["total"]
                }
    
    return patterns


def _detect_sleep_patterns(sleep_records: List) -> Dict:
    """Detect patterns in sleep data"""
    patterns = {
        "average_duration": None,
        "average_efficiency": None,
        "bedtime_patterns": {},
        "wake_time_patterns": {},
        "day_of_week_patterns": {},
        "sleep_quality_trends": []
    }
    
    durations = []
    efficiencies = []
    bedtime_hours = defaultdict(int)
    wake_hours = defaultdict(int)
    day_of_week_durations = defaultdict(list)
    
    for record in sleep_records:
        if record.sleep_duration_minutes:
            durations.append(record.sleep_duration_minutes)
        
        if record.sleep_efficiency:
            efficiencies.append(float(record.sleep_efficiency))
        
        if record.bedtime:
            bedtime_hour = record.bedtime.hour
            bedtime_hours[bedtime_hour] += 1
        
        if record.wake_time:
            wake_hour = record.wake_time.hour
            wake_hours[wake_hour] += 1
        
        if record.date and record.sleep_duration_minutes:
            day_name = record.date.strftime("%A")
            day_of_week_durations[day_name].append(record.sleep_duration_minutes)
    
    if durations:
        patterns["average_duration"] = {
            "minutes": round(mean(durations), 2),
            "hours": round(mean(durations) / 60, 2),
            "min": min(durations),
            "max": max(durations)
        }
    
    if efficiencies:
        patterns["average_efficiency"] = {
            "percentage": round(mean(efficiencies), 2),
            "min": round(min(efficiencies), 2),
            "max": round(max(efficiencies), 2)
        }
    
    # Most common bedtime hours
    if bedtime_hours:
        patterns["bedtime_patterns"] = {
            "most_common_hour": max(bedtime_hours.items(), key=lambda x: x[1])[0],
            "hour_distribution": dict(bedtime_hours)
        }
    
    # Most common wake hours
    if wake_hours:
        patterns["wake_time_patterns"] = {
            "most_common_hour": max(wake_hours.items(), key=lambda x: x[1])[0],
            "hour_distribution": dict(wake_hours)
        }
    
    # Day of week patterns
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        if day in day_of_week_durations:
            values = day_of_week_durations[day]
            patterns["day_of_week_patterns"][day] = {
                "average_duration_minutes": round(mean(values), 2),
                "average_duration_hours": round(mean(values) / 60, 2),
                "count": len(values)
            }
    
    return patterns


def _detect_exercise_patterns(exercise_records: List) -> Dict:
    """Detect patterns in exercise data"""
    patterns = {
        "frequency": {},
        "timing_patterns": {},
        "duration_patterns": {},
        "day_of_week_patterns": {}
    }
    
    exercise_hours = defaultdict(int)
    durations = []
    day_of_week_count = defaultdict(int)
    
    for record in exercise_records:
        if record.timestamp:
            hour = record.timestamp.hour
            exercise_hours[hour] += 1
            
            day_name = record.timestamp.strftime("%A")
            day_of_week_count[day_name] += 1
        
        if record.duration_minutes:
            durations.append(record.duration_minutes)
    
    patterns["frequency"] = {
        "total_sessions": len(exercise_records),
        "average_per_week": round(len(exercise_records) / max(1, len(set(r.timestamp.date() for r in exercise_records if r.timestamp)) / 7), 2) if exercise_records else 0
    }
    
    if exercise_hours:
        patterns["timing_patterns"] = {
            "most_common_hour": max(exercise_hours.items(), key=lambda x: x[1])[0],
            "hour_distribution": dict(exercise_hours)
        }
    
    if durations:
        patterns["duration_patterns"] = {
            "average_minutes": round(mean(durations), 2),
            "average_hours": round(mean(durations) / 60, 2),
            "min": min(durations),
            "max": max(durations),
            "total_minutes": sum(durations)
        }
    
    if day_of_week_count:
        patterns["day_of_week_patterns"] = dict(day_of_week_count)
    
    return patterns


@mcp.tool()
def find_correlations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    correlation_type: Optional[str] = "all"
) -> Dict:
    """
    Find correlations between different health metrics (glucose, sleep, exercise).
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        correlation_type: Type of correlations to find - "all", "exercise_glucose", "sleep_glucose", "sleep_exercise" (default: "all")
    
    Returns:
        Dictionary with correlation analysis including:
        - exercise_glucose_correlation: Correlation between exercise and glucose levels
        - sleep_glucose_correlation: Correlation between sleep quality/duration and glucose
        - sleep_exercise_correlation: Correlation between sleep and exercise patterns
        - daily_correlations: Day-by-day correlation analysis
    """
    session = None
    try:
        # Validate date parameters
        date_error = _validate_date_params(start_date, end_date)
        if date_error:
            return date_error
        
        session = db_config.get_session()
        correlations = {
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "correlation_type": correlation_type,
            "correlations": {}
        }
        
        # Apply date filters if provided
        glucose_query = session.query(Glucose)
        sleep_query = session.query(Sleep)
        exercise_query = session.query(Exercise)
        
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            
            glucose_query = glucose_query.filter(
                Glucose.timestamp >= start_dt,
                Glucose.timestamp < end_dt
            )
            sleep_query = sleep_query.filter(
                Sleep.date >= start_dt.date(),
                Sleep.date <= end_dt.date()
            )
            exercise_query = exercise_query.filter(
                Exercise.timestamp >= start_dt,
                Exercise.timestamp < end_dt
            )
        
        # Get all records
        glucose_records = glucose_query.all()
        sleep_records = sleep_query.all()
        exercise_records = exercise_query.all()
        
        # Exercise-Glucose correlation
        if correlation_type in ["all", "exercise_glucose"]:
            correlations["correlations"]["exercise_glucose"] = _correlate_exercise_glucose(
                exercise_records, glucose_records
            )
        
        # Sleep-Glucose correlation
        if correlation_type in ["all", "sleep_glucose"]:
            correlations["correlations"]["sleep_glucose"] = _correlate_sleep_glucose(
                sleep_records, glucose_records
            )
        
        # Sleep-Exercise correlation
        if correlation_type in ["all", "sleep_exercise"]:
            correlations["correlations"]["sleep_exercise"] = _correlate_sleep_exercise(
                sleep_records, exercise_records
            )
        
        # Daily correlations
        if correlation_type == "all":
            correlations["correlations"]["daily_correlations"] = _correlate_daily_metrics(
                glucose_records, sleep_records, exercise_records
            )
        
        return correlations
        
    except Exception as e:
        logger.error(f"Error finding correlations: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        if session:
            session.close()


def _correlate_exercise_glucose(exercise_records: List, glucose_records: List) -> Dict:
    """Find correlation between exercise and glucose levels"""
    if not exercise_records or not glucose_records:
        return {"error": "Insufficient data for correlation analysis"}
    
    # Group glucose by date
    glucose_by_date = defaultdict(list)
    for record in glucose_records:
        if record.timestamp and record.value:
            date_key = record.timestamp.date()
            glucose_by_date[date_key].append(float(record.value))
    
    # Group exercise by date
    exercise_by_date = defaultdict(lambda: {"duration": 0, "count": 0})
    for record in exercise_records:
        if record.timestamp:
            date_key = record.timestamp.date()
            if record.duration_minutes:
                exercise_by_date[date_key]["duration"] += record.duration_minutes
                exercise_by_date[date_key]["count"] += 1
    
    # Find days with both exercise and glucose data
    common_dates = set(glucose_by_date.keys()) & set(exercise_by_date.keys())
    
    if len(common_dates) < 3:
        return {"error": "Insufficient overlapping data for correlation analysis"}
    
    # Calculate daily averages
    exercise_durations = []
    avg_glucose = []
    max_glucose = []
    min_glucose = []
    
    for date_key in common_dates:
        exercise_durations.append(exercise_by_date[date_key]["duration"])
        glucose_values = glucose_by_date[date_key]
        avg_glucose.append(mean(glucose_values))
        max_glucose.append(max(glucose_values))
        min_glucose.append(min(glucose_values))
    
    # Calculate Pearson correlation coefficient
    def pearson_correlation(x, y):
        if len(x) != len(y) or len(x) < 2:
            return None
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        sum_y2 = sum(y[i] ** 2 for i in range(n))
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
        
        if denominator == 0:
            return None
        return numerator / denominator
    
    corr_avg = pearson_correlation(exercise_durations, avg_glucose)
    corr_max = pearson_correlation(exercise_durations, max_glucose)
    corr_min = pearson_correlation(exercise_durations, min_glucose)
    
    return {
        "days_analyzed": len(common_dates),
        "correlation_with_avg_glucose": round(corr_avg, 4) if corr_avg is not None else None,
        "correlation_with_max_glucose": round(corr_max, 4) if corr_max is not None else None,
        "correlation_with_min_glucose": round(corr_min, 4) if corr_min is not None else None,
        "interpretation": _interpret_correlation(corr_avg) if corr_avg is not None else "Insufficient data",
        "summary": {
            "avg_exercise_duration": round(mean(exercise_durations), 2) if exercise_durations else None,
            "avg_glucose_on_exercise_days": round(mean(avg_glucose), 2) if avg_glucose else None,
            "avg_glucose_on_non_exercise_days": None  # Would need additional data
        }
    }


def _correlate_sleep_glucose(sleep_records: List, glucose_records: List) -> Dict:
    """Find correlation between sleep and glucose levels"""
    if not sleep_records or not glucose_records:
        return {"error": "Insufficient data for correlation analysis"}
    
    # Group glucose by date
    glucose_by_date = defaultdict(list)
    for record in glucose_records:
        if record.timestamp and record.value:
            date_key = record.timestamp.date()
            glucose_by_date[date_key].append(float(record.value))
    
    # Group sleep by date
    sleep_by_date = {}
    for record in sleep_records:
        if record.date:
            sleep_by_date[record.date] = {
                "duration": record.sleep_duration_minutes,
                "efficiency": float(record.sleep_efficiency) if record.sleep_efficiency else None
            }
    
    # Find days with both sleep and glucose data
    common_dates = set(glucose_by_date.keys()) & set(sleep_by_date.keys())
    
    if len(common_dates) < 3:
        return {"error": "Insufficient overlapping data for correlation analysis"}
    
    # Calculate daily averages - align data by date
    sleep_durations = []
    sleep_efficiencies = []
    avg_glucose_for_duration = []
    avg_glucose_for_efficiency = []
    
    for date_key in sorted(common_dates):
        sleep_data = sleep_by_date[date_key]
        glucose_values = glucose_by_date[date_key]
        avg_glucose_value = mean(glucose_values)
        
        if sleep_data["duration"]:
            sleep_durations.append(sleep_data["duration"])
            avg_glucose_for_duration.append(avg_glucose_value)
        
        if sleep_data["efficiency"]:
            sleep_efficiencies.append(sleep_data["efficiency"])
            avg_glucose_for_efficiency.append(avg_glucose_value)
    
    # Calculate correlations
    def pearson_correlation(x, y):
        if len(x) != len(y) or len(x) < 2:
            return None
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        sum_y2 = sum(y[i] ** 2 for i in range(n))
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
        
        if denominator == 0:
            return None
        return numerator / denominator
    
    corr_duration_avg = pearson_correlation(sleep_durations, avg_glucose_for_duration)
    corr_efficiency_avg = pearson_correlation(sleep_efficiencies, avg_glucose_for_efficiency)
    
    return {
        "days_analyzed": len(common_dates),
        "correlation_sleep_duration_avg_glucose": round(corr_duration_avg, 4) if corr_duration_avg is not None else None,
        "correlation_sleep_efficiency_avg_glucose": round(corr_efficiency_avg, 4) if corr_efficiency_avg is not None else None,
        "interpretation_duration": _interpret_correlation(corr_duration_avg) if corr_duration_avg is not None else "Insufficient data",
        "interpretation_efficiency": _interpret_correlation(corr_efficiency_avg) if corr_efficiency_avg is not None else "Insufficient data",
        "summary": {
            "avg_sleep_duration_hours": round(mean(sleep_durations) / 60, 2) if sleep_durations else None,
            "avg_sleep_efficiency": round(mean(sleep_efficiencies), 2) if sleep_efficiencies else None,
            "avg_glucose": round(mean(avg_glucose_for_duration), 2) if avg_glucose_for_duration else None
        }
    }


def _correlate_sleep_exercise(sleep_records: List, exercise_records: List) -> Dict:
    """Find correlation between sleep and exercise patterns"""
    if not sleep_records or not exercise_records:
        return {"error": "Insufficient data for correlation analysis"}
    
    # Group exercise by date
    exercise_by_date = defaultdict(lambda: {"duration": 0, "count": 0})
    for record in exercise_records:
        if record.timestamp:
            date_key = record.timestamp.date()
            if record.duration_minutes:
                exercise_by_date[date_key]["duration"] += record.duration_minutes
                exercise_by_date[date_key]["count"] += 1
    
    # Group sleep by date
    sleep_by_date = {}
    for record in sleep_records:
        if record.date:
            sleep_by_date[record.date] = {
                "duration": record.sleep_duration_minutes,
                "efficiency": float(record.sleep_efficiency) if record.sleep_efficiency else None
            }
    
    # Find days with both sleep and exercise data
    common_dates = set(exercise_by_date.keys()) & set(sleep_by_date.keys())
    
    if len(common_dates) < 3:
        return {"error": "Insufficient overlapping data for correlation analysis"}
    
    # Calculate daily values
    exercise_durations = []
    sleep_durations = []
    sleep_efficiencies = []
    
    for date_key in common_dates:
        exercise_durations.append(exercise_by_date[date_key]["duration"])
        sleep_data = sleep_by_date[date_key]
        if sleep_data["duration"]:
            sleep_durations.append(sleep_data["duration"])
        if sleep_data["efficiency"]:
            sleep_efficiencies.append(sleep_data["efficiency"])
    
    # Calculate correlations
    def pearson_correlation(x, y):
        if len(x) != len(y) or len(x) < 2:
            return None
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        sum_y2 = sum(y[i] ** 2 for i in range(n))
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
        
        if denominator == 0:
            return None
        return numerator / denominator
    
    corr_duration = pearson_correlation(exercise_durations, sleep_durations) if len(exercise_durations) == len(sleep_durations) else None
    corr_efficiency = pearson_correlation(exercise_durations, sleep_efficiencies) if len(exercise_durations) == len(sleep_efficiencies) else None
    
    return {
        "days_analyzed": len(common_dates),
        "correlation_exercise_sleep_duration": round(corr_duration, 4) if corr_duration is not None else None,
        "correlation_exercise_sleep_efficiency": round(corr_efficiency, 4) if corr_efficiency is not None else None,
        "interpretation_duration": _interpret_correlation(corr_duration) if corr_duration is not None else "Insufficient data",
        "interpretation_efficiency": _interpret_correlation(corr_efficiency) if corr_efficiency is not None else "Insufficient data"
    }


def _correlate_daily_metrics(glucose_records: List, sleep_records: List, exercise_records: List) -> Dict:
    """Find daily correlations across all metrics"""
    # This is a simplified version - could be expanded
    return {
        "summary": "Daily correlation analysis across glucose, sleep, and exercise metrics",
        "note": "Use specific correlation types for detailed analysis"
    }


def _interpret_correlation(corr: float) -> str:
    """Interpret correlation coefficient"""
    if corr is None:
        return "Insufficient data"
    
    abs_corr = abs(corr)
    direction = "positive" if corr > 0 else "negative"
    
    if abs_corr >= 0.7:
        strength = "strong"
    elif abs_corr >= 0.4:
        strength = "moderate"
    elif abs_corr >= 0.2:
        strength = "weak"
    else:
        strength = "very weak or no"
    
    return f"{strength} {direction} correlation (r={corr:.3f})"


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
    logger.info("📊 Available tools: get_glucose_data, get_sleep_data, get_exercise_data, detect_patterns, find_correlations")
    
    # Start MCP server (blocks and handles stdio communication)
    mcp.run(transport='stdio')
