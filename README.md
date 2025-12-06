# Patient Summary MCP Server

MCP server for diabetes patient data analysis with Amazon RDS MySQL backend.

## Features
- Patient summary retrieval with date filtering
- Anomaly detection for glucose readings
- Hypoglycemic event tracking
- Glucose pattern analysis (hourly patterns, dawn phenomenon)
- Real-time CGM data ingestion (5-minute intervals)
- Time-in-range calculations

## Architecture
- **server.py**: Main MCP server with Flask API for real-time data ingestion
- **patient_data.py**: Data processing and analysis functions
- **db_config.py**: Amazon RDS MySQL database configuration
- **manifest.json**: MCP server configuration for Claude Desktop

## Database Setup (Amazon RDS MySQL)

### Prerequisites
1. Amazon RDS MySQL instance running
2. Database created (default: `diabetes_cgm`)
3. User credentials with appropriate permissions

### Configuration

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   
   Create a `.env` file in the project root:
   ```bash
   RDS_HOST=your-rds-endpoint.region.rds.amazonaws.com
   RDS_PORT=3306
   RDS_USER=admin
   RDS_PASSWORD=your-secure-password
   RDS_DATABASE=diabetes_cgm
   ```

   Or set environment variables directly:
   ```bash
   export RDS_HOST=your-rds-endpoint.region.rds.amazonaws.com
   export RDS_PORT=3306
   export RDS_USER=admin
   export RDS_PASSWORD=your-secure-password
   export RDS_DATABASE=diabetes_cgm
   ```

3. **Database tables will be created automatically** on first run

### Database Schema

The following tables are created automatically:
- **`glucose`**: Glucose/CGM readings with timestamps, values, and metadata
- **`sleep`**: Sleep data with start/end times, duration, and sleep stages
- **`exercise`**: Exercise/workout data with type, duration, distance, and energy burned

## Running the Server

```bash
python server.py
```

Or use the startup script:
```bash
./start_server.sh
```

## MCP Tools

The server exposes the following MCP tools:

### Data Retrieval from RDS:
- `get_glucose_data`: Retrieve glucose data from RDS MySQL (with optional date filtering)
- `get_sleep_data`: Retrieve sleep data from RDS MySQL (with optional date filtering)
- `get_exercise_data`: Retrieve exercise/workout data from RDS MySQL (with optional date filtering)

### Analysis Tools:
- `get_patient_summary`: Retrieve patient glucose readings
- `detect_anomalous_glucose_events`: Find statistical anomalies
- `find_last_hypoglycemic_event`: Track hypo events
- `analyze_glucose_patterns`: Pattern analysis
- `get_live_cgm_data`: Real-time CGM readings
- `get_cgm_monitoring_status`: System status

## API Endpoints

- `POST /health-data`: Receive CGM data from Health Auto Export
- `GET /cgm-status`: Get current monitoring status 
            