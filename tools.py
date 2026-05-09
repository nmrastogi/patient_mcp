#!/usr/bin/env python3
"""
Health data query tools for the Claude AI agent.
Identical logic to mcp_server.py but with no MCP/pydantic dependency
so it runs cleanly on AWS Lambda.
"""
from db_config import db_config
from models import Glucose, Sleep, Exercise
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Type
from sqlalchemy.orm import Query
from collections import defaultdict, Counter
from statistics import mean
import logging
import math

try:
    from zoneinfo import ZoneInfo
    _PACIFIC = ZoneInfo("America/Los_Angeles")
    def _to_pacific(dt: datetime) -> str:
        if dt is None:
            return None
        utc = dt.replace(tzinfo=timezone.utc)
        return utc.astimezone(_PACIFIC).strftime("%Y-%m-%d %H:%M %Z")
    def _str_to_pacific(s: str) -> str:
        if not s:
            return s
        try:
            return _to_pacific(datetime.fromisoformat(s))
        except Exception:
            return s
except Exception:
    def _to_pacific(dt: datetime) -> str:
        if dt is None:
            return None
        return (dt - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M PDT")
    def _str_to_pacific(s: str) -> str:
        if not s:
            return s
        try:
            dt = datetime.fromisoformat(s)
            return (dt - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M PDT")
        except Exception:
            return s

# Fields in to_dict() output that hold UTC datetime strings and need conversion
_UTC_DATETIME_FIELDS = {
    'timestamp', 'bedtime', 'wake_time', 'start_time', 'end_time', 'created_at', 'updated_at'
}

def _localize(record: dict) -> dict:
    """Convert UTC datetime strings to Pacific time in a to_dict() record."""
    return {
        k: _str_to_pacific(v) if k in _UTC_DATETIME_FIELDS and isinstance(v, str) else v
        for k, v in record.items()
    }

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _validate_date_params(start_date, end_date):
    if start_date and not end_date:
        return {"error": "Both start_date and end_date must be provided together"}
    if end_date and not start_date:
        return {"error": "Both start_date and end_date must be provided together"}
    return None


def _validate_limit(limit):
    if limit is not None and limit < 1:
        return {"error": "Limit must be greater than 0 or None"}
    return None


def _parse_dates(start_date, end_date, use_date_field=False):
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if start_dt > end_dt:
            return {"error": "start_date must be before or equal to end_date"}
        if use_date_field:
            return (start_dt.date(), end_dt.date())
        return (start_dt, end_dt + timedelta(days=1))
    except ValueError as e:
        return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD format"}


def _apply_date_filter(query, model_class, start_date, end_date):
    if not (start_date and end_date):
        return query, None
    has_date_field = hasattr(model_class, 'date')
    date_result = _parse_dates(start_date, end_date, use_date_field=has_date_field)
    if isinstance(date_result, dict):
        return query, date_result
    start_dt, end_dt = date_result
    if has_date_field:
        query = query.filter(model_class.date >= start_dt, model_class.date <= end_dt)
    else:
        query = query.filter(model_class.timestamp >= start_dt, model_class.timestamp < end_dt)
    return query, None


def _get_data_generic(model_class, table_name, order_by_field,
                      start_date=None, end_date=None, limit=None):
    session = None
    try:
        err = _validate_limit(limit) or _validate_date_params(start_date, end_date)
        if err:
            return err
        session = db_config.get_session()
        query = session.query(model_class)
        query, err = _apply_date_filter(query, model_class, start_date, end_date)
        if err:
            return err
        order_field = getattr(model_class, order_by_field)
        query = query.order_by(order_field.desc())
        effective_limit = min(limit, 500) if limit is not None else 200
        results = query.limit(effective_limit).all()
        data = [_localize(r.to_dict()) for r in results]
        return {
            "table": table_name,
            "total_records": len(data),
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "limit": effective_limit,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Error getting {table_name} data: {e}", exc_info=True)
        return {"error": str(e), "table": table_name}
    finally:
        if session:
            session.close()


# ---------------------------------------------------------------------------
# Public tool functions (called by health_agent.py)
# ---------------------------------------------------------------------------

def get_glucose_data(start_date=None, end_date=None, limit=None):
    return _get_data_generic(Glucose, "blood_glucose", "timestamp",
                             start_date, end_date, limit)


def get_sleep_data(start_date=None, end_date=None, limit=None):
    return _get_data_generic(Sleep, "sleep_data", "bedtime",
                             start_date, end_date, limit)


def get_exercise_data(start_date=None, end_date=None, limit=None):
    return _get_data_generic(Exercise, "exercise_data", "timestamp",
                             start_date, end_date, limit)


def detect_patterns(start_date=None, end_date=None, pattern_type="all"):
    session = None
    try:
        err = _validate_date_params(start_date, end_date)
        if err:
            return err
        session = db_config.get_session()
        patterns = {
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "pattern_type": pattern_type,
            "patterns": {},
        }
        gq = session.query(Glucose)
        sq = session.query(Sleep)
        eq = session.query(Exercise)
        if start_date and end_date:
            s = datetime.strptime(start_date, '%Y-%m-%d')
            e = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            gq = gq.filter(Glucose.timestamp >= s, Glucose.timestamp < e)
            sq = sq.filter(Sleep.date >= s.date(), Sleep.date <= e.date())
            eq = eq.filter(Exercise.timestamp >= s, Exercise.timestamp < e)
        if pattern_type in ["all", "glucose", "temporal"]:
            recs = gq.all()
            if recs:
                patterns["patterns"]["glucose"] = _detect_glucose_patterns(recs)
        if pattern_type in ["all", "sleep", "temporal"]:
            recs = sq.all()
            if recs:
                patterns["patterns"]["sleep"] = _detect_sleep_patterns(recs)
        if pattern_type in ["all", "exercise", "temporal"]:
            recs = eq.all()
            if recs:
                patterns["patterns"]["exercise"] = _detect_exercise_patterns(recs)
        return patterns
    except Exception as e:
        logger.error(f"Error detecting patterns: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        if session:
            session.close()


def find_correlations(start_date=None, end_date=None, correlation_type="all"):
    session = None
    try:
        err = _validate_date_params(start_date, end_date)
        if err:
            return err
        session = db_config.get_session()
        result = {
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "all dates",
            "correlation_type": correlation_type,
            "correlations": {},
        }
        gq = session.query(Glucose)
        sq = session.query(Sleep)
        eq = session.query(Exercise)
        if start_date and end_date:
            s = datetime.strptime(start_date, '%Y-%m-%d')
            e = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            gq = gq.filter(Glucose.timestamp >= s, Glucose.timestamp < e)
            sq = sq.filter(Sleep.date >= s.date(), Sleep.date <= e.date())
            eq = eq.filter(Exercise.timestamp >= s, Exercise.timestamp < e)
        g, sl, ex = gq.all(), sq.all(), eq.all()
        if correlation_type in ["all", "exercise_glucose"]:
            result["correlations"]["exercise_glucose"] = _correlate_exercise_glucose(ex, g)
        if correlation_type in ["all", "sleep_glucose"]:
            result["correlations"]["sleep_glucose"] = _correlate_sleep_glucose(sl, g)
        if correlation_type in ["all", "sleep_exercise"]:
            result["correlations"]["sleep_exercise"] = _correlate_sleep_exercise(sl, ex)
        return result
    except Exception as e:
        logger.error(f"Error finding correlations: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        if session:
            session.close()


# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

def _detect_glucose_patterns(records):
    hourly = defaultdict(list)
    dow = defaultdict(list)
    highs, lows = [], []
    tir = defaultdict(lambda: {"in_range": 0, "total": 0})
    for r in records:
        if not r.value:
            continue
        v = float(r.value)
        h = r.timestamp.hour
        hourly[h].append(v)
        dow[r.timestamp.strftime("%A")].append(v)
        tir[h]["total"] += 1
        if 70 <= v <= 180:
            tir[h]["in_range"] += 1
        if v > 180:
            highs.append({"timestamp_pt": _to_pacific(r.timestamp), "value": v, "hour_utc": h})
        if v < 70:
            lows.append({"timestamp_pt": _to_pacific(r.timestamp), "value": v, "hour_utc": h})
    return {
        "hourly_averages": {h: {"average": round(mean(vs), 2), "count": len(vs)} for h, vs in hourly.items()},
        "day_of_week_averages": {d: {"average": round(mean(vs), 2), "count": len(vs)} for d, vs in dow.items()},
        "high_glucose_times": [{"hour": h, "count": c} for h, c in Counter(p["hour_utc"] for p in highs).most_common(5)],
        "low_glucose_times": [{"hour": h, "count": c} for h, c in Counter(p["hour_utc"] for p in lows).most_common(5)],
        "time_in_range_by_hour": {h: {"percentage": round(d["in_range"] / d["total"] * 100, 2), "total_readings": d["total"]} for h, d in tir.items() if d["total"] > 0},
    }


def _detect_sleep_patterns(records):
    durations, efficiencies = [], []
    bedtime_hours, wake_hours = defaultdict(int), defaultdict(int)
    dow = defaultdict(list)
    for r in records:
        if r.sleep_duration_minutes:
            durations.append(r.sleep_duration_minutes)
        if r.sleep_efficiency:
            efficiencies.append(float(r.sleep_efficiency))
        if r.bedtime:
            # Convert UTC bedtime to Pacific before bucketing by hour
            pt_bedtime = r.bedtime - timedelta(hours=7)  # approximate PDT
            bedtime_hours[pt_bedtime.hour] += 1
        if r.wake_time:
            pt_wake = r.wake_time - timedelta(hours=7)
            wake_hours[pt_wake.hour] += 1
        if r.date and r.sleep_duration_minutes:
            dow[r.date.strftime("%A")].append(r.sleep_duration_minutes)
    return {
        "average_duration": {"minutes": round(mean(durations), 2), "hours": round(mean(durations) / 60, 2)} if durations else None,
        "average_efficiency": {"percentage": round(mean(efficiencies), 2)} if efficiencies else None,
        "bedtime_patterns": {"most_common_hour": max(bedtime_hours, key=bedtime_hours.get)} if bedtime_hours else {},
        "wake_time_patterns": {"most_common_hour": max(wake_hours, key=wake_hours.get)} if wake_hours else {},
        "day_of_week_patterns": {d: {"average_duration_hours": round(mean(vs) / 60, 2), "count": len(vs)} for d, vs in dow.items()},
    }


def _detect_exercise_patterns(records):
    hours, durations, dow = defaultdict(int), [], defaultdict(int)
    for r in records:
        if r.timestamp:
            hours[r.timestamp.hour] += 1
            dow[r.timestamp.strftime("%A")] += 1
        if r.duration_minutes:
            durations.append(r.duration_minutes)
    return {
        "frequency": {"total_sessions": len(records)},
        "timing_patterns": {"most_common_hour": max(hours, key=hours.get)} if hours else {},
        "duration_patterns": {"average_minutes": round(mean(durations), 2), "total_minutes": sum(durations)} if durations else {},
        "day_of_week_patterns": dict(dow),
    }


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------

def _pearson(x, y):
    if len(x) != len(y) or len(x) < 2:
        return None
    n = len(x)
    sx, sy = sum(x), sum(y)
    sxy = sum(x[i] * y[i] for i in range(n))
    sx2 = sum(v ** 2 for v in x)
    sy2 = sum(v ** 2 for v in y)
    denom = math.sqrt((n * sx2 - sx ** 2) * (n * sy2 - sy ** 2))
    return (n * sxy - sx * sy) / denom if denom else None


def _interpret(corr):
    if corr is None:
        return "Insufficient data"
    a = abs(corr)
    d = "positive" if corr > 0 else "negative"
    s = "strong" if a >= 0.7 else "moderate" if a >= 0.4 else "weak" if a >= 0.2 else "very weak or no"
    return f"{s} {d} correlation (r={corr:.3f})"


def _correlate_exercise_glucose(ex, gl):
    if not ex or not gl:
        return {"error": "Insufficient data"}
    gbd = defaultdict(list)
    for r in gl:
        if r.timestamp and r.value:
            gbd[r.timestamp.date()].append(float(r.value))
    ebd = defaultdict(int)
    for r in ex:
        if r.timestamp and r.duration_minutes:
            ebd[r.timestamp.date()] += r.duration_minutes
    common = set(gbd) & set(ebd)
    if len(common) < 3:
        return {"error": "Insufficient overlapping data"}
    ed = [ebd[d] for d in common]
    ag = [mean(gbd[d]) for d in common]
    c = _pearson(ed, ag)
    return {"days_analyzed": len(common), "correlation_with_avg_glucose": round(c, 4) if c else None, "interpretation": _interpret(c)}


def _correlate_sleep_glucose(sl, gl):
    if not sl or not gl:
        return {"error": "Insufficient data"}
    gbd = defaultdict(list)
    for r in gl:
        if r.timestamp and r.value:
            gbd[r.timestamp.date()].append(float(r.value))
    sbd = {r.date: r.sleep_duration_minutes for r in sl if r.date and r.sleep_duration_minutes}
    common = set(gbd) & set(sbd)
    if len(common) < 3:
        return {"error": "Insufficient overlapping data"}
    sd = [sbd[d] for d in common]
    ag = [mean(gbd[d]) for d in common]
    c = _pearson(sd, ag)
    return {"days_analyzed": len(common), "correlation_sleep_duration_avg_glucose": round(c, 4) if c else None, "interpretation_duration": _interpret(c)}


def _correlate_sleep_exercise(sl, ex):
    if not sl or not ex:
        return {"error": "Insufficient data"}
    ebd = defaultdict(int)
    for r in ex:
        if r.timestamp and r.duration_minutes:
            ebd[r.timestamp.date()] += r.duration_minutes
    sbd = {r.date: r.sleep_duration_minutes for r in sl if r.date and r.sleep_duration_minutes}
    common = set(ebd) & set(sbd)
    if len(common) < 3:
        return {"error": "Insufficient overlapping data"}
    ed = [ebd[d] for d in common]
    sd = [sbd[d] for d in common]
    c = _pearson(ed, sd)
    return {"days_analyzed": len(common), "correlation_exercise_sleep_duration": round(c, 4) if c else None, "interpretation_duration": _interpret(c)}