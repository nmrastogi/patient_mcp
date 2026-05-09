#!/usr/bin/env python3
"""
REST API for Diabetes Health Data
- POST /api/glucose  : Receive glucose data from Health Auto Export app
- POST /api/sleep    : Receive sleep data from Health Auto Export app
- POST /api/exercise : Receive exercise data from Health Auto Export app
- GET  /api/glucose  : Read glucose records (optional: start_date, end_date, limit)
- GET  /api/sleep    : Read sleep records (optional: start_date, end_date, limit)
- GET  /api/exercise : Read exercise records (optional: start_date, end_date, limit)
- GET  /api/health   : Health check
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from sqlalchemy import func
from db_config import db_config
from models import BloodGlucose, SleepData, ExerciseData, AIInsight
from health_agent import chat as agent_chat, generate_insights as agent_generate_insights
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_int(val):
    try:
        return int(val) if val not in (None, '') else None
    except (ValueError, TypeError):
        return None


def _parse_float(val):
    try:
        return float(val) if val not in (None, '') else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# POST – ingest data from Health Auto Export app
# ---------------------------------------------------------------------------

@app.route('/api/glucose', methods=['POST'])
def receive_glucose():
    """Receive blood glucose data from Health Auto Export app"""
    try:
        data = request.get_json()
        logger.info(f"📥 Glucose payload received")

        records = []
        if data and 'data' in data and 'metrics' in data['data']:
            for metric in data['data']['metrics']:
                for item in metric.get('data', []):
                    timestamp = item.get('date') or item.get('timestamp')
                    value = _parse_float(item.get('qty') or item.get('value'))
                    if not timestamp or not value or value <= 0:
                        continue
                    records.append(BloodGlucose(
                        timestamp=datetime.fromisoformat(timestamp),
                        value=value,
                        unit=item.get('unit', 'mg/dL') or 'mg/dL',
                    ))

        if not records:
            return jsonify({'status': 'warning', 'message': 'No valid glucose records'}), 200

        session = db_config.get_session()
        try:
            from sqlalchemy import text
            sql = text("""
                INSERT IGNORE INTO blood_glucose (timestamp, value, unit)
                VALUES (:timestamp, :value, :unit)
            """)
            for r in records:
                session.execute(sql, {'timestamp': r.timestamp, 'value': float(r.value), 'unit': r.unit})
            session.commit()
            logger.info(f"✅ Saved {len(records)} glucose records (duplicates silently skipped)")
            return jsonify({'status': 'success', 'saved': len(records)}), 200
        finally:
            session.close()

    except Exception as e:
        logger.error(f"❌ Error saving glucose data: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sleep', methods=['POST'])
def receive_sleep():
    """Receive sleep data from Health Auto Export app"""
    try:
        data = request.get_json()
        logger.info(f"📥 Sleep payload received")

        records = []
        if data and 'data' in data and 'metrics' in data['data']:
            for metric in data['data']['metrics']:
                for item in metric.get('data', []):
                    date_str = (item.get('date') or '').split()[0]
                    if not date_str:
                        continue

                    # Accept both camelCase (iOS default) and snake_case
                    bedtime_str = item.get('inBedStart') or item.get('in_bed_start')
                    wake_str    = item.get('inBedEnd')   or item.get('in_bed_end')
                    total_sleep = item.get('totalSleep') or item.get('total_sleep')

                    records.append(SleepData(
                        date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                        bedtime=datetime.fromisoformat(bedtime_str) if bedtime_str else None,
                        wake_time=datetime.fromisoformat(wake_str) if wake_str else None,
                        # iOS sends minutes — do NOT multiply by 60
                        sleep_duration_minutes=_parse_int(total_sleep) if total_sleep else None,
                        deep_sleep_minutes=_parse_int(item.get('deep')) if item.get('deep') else None,
                        light_sleep_minutes=_parse_int(item.get('core')) if item.get('core') else None,
                        rem_sleep_minutes=_parse_int(item.get('rem')) if item.get('rem') else None,
                    ))

        if not records:
            return jsonify({'status': 'warning', 'message': 'No valid sleep records'}), 200

        session = db_config.get_session()
        try:
            for r in records:
                existing = session.query(SleepData).filter_by(date=r.date).first()
                if existing:
                    existing.sleep_duration_minutes = r.sleep_duration_minutes
                    existing.deep_sleep_minutes     = r.deep_sleep_minutes
                    existing.light_sleep_minutes    = r.light_sleep_minutes
                    existing.rem_sleep_minutes      = r.rem_sleep_minutes
                    if r.bedtime:   existing.bedtime    = r.bedtime
                    if r.wake_time: existing.wake_time  = r.wake_time
                else:
                    session.add(r)
            session.commit()
            logger.info(f"✅ Saved/updated {len(records)} sleep records")
            return jsonify({'status': 'success', 'saved': len(records)}), 200
        finally:
            session.close()

    except Exception as e:
        logger.error(f"❌ Error saving sleep data: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/exercise', methods=['POST'])
def receive_exercise():
    """Receive exercise/workout data from Health Auto Export app"""
    try:
        data = request.get_json()
        logger.info(f"📥 Exercise payload received")

        records = []

        if data and 'data' in data:
            # Workout format (with metadata)
            if 'workouts' in data['data']:
                for w in data['data']['workouts']:
                    timestamp = w.get('start')
                    if not timestamp:
                        continue
                    records.append(ExerciseData(
                        timestamp=datetime.fromisoformat(timestamp),
                        duration_minutes=_parse_int(w.get('duration')),
                    ))

            # Metrics format (apple_exercise_time)
            elif 'metrics' in data['data']:
                for metric in data['data']['metrics']:
                    for item in metric.get('data', []):
                        timestamp = item.get('date')
                        if not timestamp:
                            continue
                        records.append(ExerciseData(
                            timestamp=datetime.fromisoformat(timestamp),
                            duration_minutes=_parse_int(item.get('qty')),
                        ))

        if not records:
            return jsonify({'status': 'warning', 'message': 'No valid exercise records'}), 200

        session = db_config.get_session()
        try:
            from sqlalchemy import text
            sql = text("""
                INSERT IGNORE INTO exercise_data (timestamp, duration_minutes)
                VALUES (:timestamp, :duration)
            """)
            for r in records:
                session.execute(sql, {'timestamp': r.timestamp, 'duration': r.duration_minutes})
            session.commit()
            logger.info(f"✅ Saved {len(records)} exercise records (duplicates silently skipped)")
            return jsonify({'status': 'success', 'saved': len(records)}), 200
        finally:
            session.close()

    except Exception as e:
        logger.error(f"❌ Error saving exercise data: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# GET – read data from RDS
# ---------------------------------------------------------------------------

def _read_records(model_class, date_field, start_date, end_date, limit):
    """Generic read helper"""
    session = db_config.get_session()
    try:
        query = session.query(model_class)

        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            field = getattr(model_class, date_field)
            if date_field == 'date':
                query = query.filter(field >= start_dt.date(), field <= end_dt.date())
            else:
                from datetime import timedelta
                query = query.filter(field >= start_dt, field < end_dt + timedelta(days=1))

        order_field = getattr(model_class, date_field)
        query = query.order_by(order_field.desc())

        if limit:
            query = query.limit(int(limit))

        results = query.all()
        return [r.to_dict() for r in results]
    finally:
        session.close()


@app.route('/api/glucose', methods=['GET'])
def get_glucose():
    """Read glucose records. Query params: start_date, end_date, limit"""
    try:
        data = _read_records(
            BloodGlucose, 'timestamp',
            request.args.get('start_date'),
            request.args.get('end_date'),
            request.args.get('limit')
        )
        return jsonify({'status': 'success', 'total': len(data), 'data': data}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sleep', methods=['GET'])
def get_sleep():
    """Read sleep records. Query params: start_date, end_date, limit"""
    try:
        data = _read_records(
            SleepData, 'date',
            request.args.get('start_date'),
            request.args.get('end_date'),
            request.args.get('limit')
        )
        return jsonify({'status': 'success', 'total': len(data), 'data': data}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/exercise', methods=['GET'])
def get_exercise():
    """Read exercise records. Query params: start_date, end_date, limit"""
    try:
        data = _read_records(
            ExerciseData, 'timestamp',
            request.args.get('start_date'),
            request.args.get('end_date'),
            request.args.get('limit')
        )
        return jsonify({'status': 'success', 'total': len(data), 'data': data}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    db_ok = db_config.test_connection()
    return jsonify({
        'status': 'ok',
        'database': 'connected' if db_ok else 'disconnected',
        'endpoints': {
            'POST /api/glucose': 'Ingest glucose data',
            'POST /api/sleep': 'Ingest sleep data',
            'POST /api/exercise': 'Ingest exercise data',
            'GET  /api/glucose': 'Read glucose data',
            'GET  /api/sleep': 'Read sleep data',
            'GET  /api/exercise': 'Read exercise data',
        }
    }), 200


# ---------------------------------------------------------------------------
# URL aliases — iOS calls these paths (no /api/ prefix)
# ---------------------------------------------------------------------------

@app.route('/glucose', methods=['GET'])
def get_glucose_alias():
    return get_glucose()

@app.route('/sleep', methods=['GET'])
def get_sleep_alias():
    return get_sleep()

@app.route('/exercise', methods=['GET'])
def get_exercise_alias():
    return get_exercise()

@app.route('/glucose/ingest', methods=['POST'])
def ingest_glucose_alias():
    return receive_glucose()

@app.route('/sleep/ingest', methods=['POST'])
def ingest_sleep_alias():
    return receive_sleep()

@app.route('/exercise/ingest', methods=['POST'])
def ingest_exercise_alias():
    return receive_exercise()


# ---------------------------------------------------------------------------
# AI Agent endpoints
# ---------------------------------------------------------------------------

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Run Claude AI agent to answer a health question."""
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'status': 'error', 'message': 'question is required'}), 400
    result = agent_chat(question, conversation_history=data.get('history', []))
    return jsonify(result), 200


@app.route('/insights', methods=['GET'])
def get_insights():
    """Return stored AI insights, newest first."""
    limit = _parse_int(request.args.get('limit')) or 20
    session = db_config.get_session()
    try:
        rows = (session.query(AIInsight)
                .order_by(AIInsight.created_at.desc())
                .limit(limit)
                .all())
        data = [r.to_dict() for r in rows]
    finally:
        session.close()
    return jsonify({'status': 'success', 'total': len(data), 'data': data}), 200


@app.route('/insights/generate', methods=['POST'])
def generate_insights_endpoint():
    """Trigger Claude agent to generate weekly insights and store them."""
    raw = agent_generate_insights()
    session = db_config.get_session()
    try:
        session.query(AIInsight).delete()
        for item in raw:
            session.add(AIInsight(
                insight_type=item['insight_type'],
                week_start=(datetime.strptime(item['week_start'], '%Y-%m-%d').date()
                            if item.get('week_start') else None),
                content=item['content'],
            ))
        session.commit()
    finally:
        session.close()
    return jsonify({'status': 'success', 'generated': len(raw), 'data': raw}), 200


@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Return aggregated health summary for the last N days."""
    days = _parse_int(request.args.get('days')) or 7
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    session = db_config.get_session()
    try:
        glucose_vals = [
            float(r.value) for r in
            session.query(BloodGlucose)
            .filter(BloodGlucose.timestamp >= start_dt, BloodGlucose.timestamp <= end_dt)
            .all() if r.value
        ]
        sleep_mins = [
            r.sleep_duration_minutes for r in
            session.query(SleepData)
            .filter(SleepData.date >= start_dt.date(), SleepData.date <= end_dt.date())
            .all() if r.sleep_duration_minutes
        ]
        exercise_total = sum(
            r.duration_minutes for r in
            session.query(ExerciseData)
            .filter(ExerciseData.timestamp >= start_dt, ExerciseData.timestamp <= end_dt)
            .all() if r.duration_minutes and r.duration_minutes > 10
        )
        data_oldest = session.query(func.min(BloodGlucose.timestamp)).scalar()
        data_latest = session.query(func.max(BloodGlucose.timestamp)).scalar()
    finally:
        session.close()

    avg_glucose   = round(sum(glucose_vals) / len(glucose_vals), 1) if glucose_vals else None
    in_range      = sum(1 for v in glucose_vals if 70 <= v <= 180)
    time_in_range = round(in_range / len(glucose_vals) * 100, 1) if glucose_vals else None
    avg_sleep     = round(sum(sleep_mins) / len(sleep_mins) / 60.0, 2) if sleep_mins else None

    return jsonify({
        'avg_glucose':            avg_glucose,
        'time_in_range':          time_in_range,
        'avg_sleep_hours':        avg_sleep,
        'total_exercise_minutes': exercise_total or None,
        'period_days':            days,
        'data_start':             data_oldest.isoformat() if data_oldest else None,
        'data_end':               data_latest.isoformat() if data_latest else None,
        'status':                 'success',
    }), 200


# ---------------------------------------------------------------------------
# Lambda entry point — custom zero-dependency WSGI adapter for API Gateway
# ---------------------------------------------------------------------------

import io as _io
import base64 as _base64


def handler(event, context):
    """AWS Lambda handler for API Gateway HTTP API (payload format 2.0)."""
    http    = event.get('requestContext', {}).get('http', {})
    method  = http.get('method', 'GET')
    path    = event.get('rawPath', '/')
    query   = event.get('rawQueryString', '') or ''
    headers = event.get('headers', {}) or {}
    body    = event.get('body', '') or ''

    if event.get('isBase64Encoded'):
        body = _base64.b64decode(body)
    elif isinstance(body, str):
        body = body.encode('utf-8')

    environ = {
        'REQUEST_METHOD':    method,
        'PATH_INFO':         path,
        'QUERY_STRING':      query,
        'CONTENT_TYPE':      headers.get('content-type', ''),
        'CONTENT_LENGTH':    str(len(body)),
        'wsgi.input':        _io.BytesIO(body),
        'wsgi.errors':       __import__('sys').stderr,
        'wsgi.url_scheme':   'https',
        'wsgi.multithread':  False,
        'wsgi.multiprocess': False,
        'wsgi.run_once':     False,
        'SERVER_NAME':       'lambda',
        'SERVER_PORT':       '443',
        'SERVER_PROTOCOL':   'HTTP/1.1',
    }
    for k, v in headers.items():
        environ[f'HTTP_{k.upper().replace("-", "_")}'] = v

    response = {'statusCode': 500, 'headers': {}, 'body': ''}

    def start_response(status, response_headers, exc_info=None):
        response['statusCode'] = int(status.split(' ', 1)[0])
        response['headers'] = dict(response_headers)

    result = app(environ, start_response)
    response['body'] = b''.join(result).decode('utf-8')
    return response


if __name__ == '__main__':
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 5001))
    logger.info(f"🚀 Starting REST API on {host}:{port}")
    app.run(host=host, port=port, debug=False)
