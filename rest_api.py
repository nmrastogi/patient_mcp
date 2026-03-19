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
from datetime import datetime
from db_config import db_config
from models import BloodGlucose, SleepData, ExerciseData
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
            for r in records:
                session.merge(r)
            session.commit()
            logger.info(f"✅ Saved {len(records)} glucose records")
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

                    bedtime_str = item.get('inBedStart')
                    wake_str = item.get('inBedEnd')

                    records.append(SleepData(
                        date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                        bedtime=datetime.fromisoformat(bedtime_str) if bedtime_str else None,
                        wake_time=datetime.fromisoformat(wake_str) if wake_str else None,
                        sleep_duration_minutes=_parse_int(item.get('totalSleep', 0) * 60) if item.get('totalSleep') else None,
                        deep_sleep_minutes=_parse_int(item.get('deep', 0) * 60) if item.get('deep') else None,
                        light_sleep_minutes=_parse_int(item.get('core', 0) * 60) if item.get('core') else None,
                        rem_sleep_minutes=_parse_int(item.get('rem', 0) * 60) if item.get('rem') else None,
                    ))

        if not records:
            return jsonify({'status': 'warning', 'message': 'No valid sleep records'}), 200

        session = db_config.get_session()
        try:
            for r in records:
                session.merge(r)
            session.commit()
            logger.info(f"✅ Saved {len(records)} sleep records")
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
                    calories = _parse_float(
                        w.get('activeEnergyBurned', {}).get('qty') if isinstance(w.get('activeEnergyBurned'), dict) else w.get('activeEnergyBurned')
                    )
                    records.append(ExerciseData(
                        timestamp=datetime.fromisoformat(timestamp),
                        activity_type=w.get('workoutName') or w.get('workoutActivityType'),
                        duration_minutes=_parse_int(w.get('duration')),
                        calories_burned=calories,
                        active_energy_kcal=calories,
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
                            activity_type='Exercise',
                            duration_minutes=_parse_int(item.get('qty')),
                        ))

        if not records:
            return jsonify({'status': 'warning', 'message': 'No valid exercise records'}), 200

        session = db_config.get_session()
        try:
            for r in records:
                session.merge(r)
            session.commit()
            logger.info(f"✅ Saved {len(records)} exercise records")
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


if __name__ == '__main__':
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 5001))
    logger.info(f"🚀 Starting REST API on {host}:{port}")
    app.run(host=host, port=port, debug=False)
