# Diabetes Data MCP Server

MCP server for diabetes patient data analysis with Amazon RDS MySQL backend. Provides tools for retrieving and analyzing glucose, sleep, and exercise data.

## Features

- **Data Retrieval**: Query glucose, sleep, and exercise data from RDS MySQL with date filtering
- **Pattern Detection**: Identify temporal patterns, behavioral patterns, and trends in health data
- **Correlation Analysis**: Find correlations between exercise, sleep, and glucose metrics
- **Unlimited Data Access**: No default limits on data retrieval (optional limit parameter)
- **SQLAlchemy ORM**: Type-safe database queries with automatic schema mapping

## Architecture

- **`mcp_server.py`**: Main MCP server with 5 tools for data retrieval and analysis
- **`models.py`**: SQLAlchemy ORM models for database tables
- **`db_config.py`**: Amazon RDS MySQL database configuration and connection management
- **`tests/`**: Pytest test suite for database and MCP tool functionality

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

3. **Database tables** should already exist in RDS (not created automatically)

### Database Schema

The server connects to the following tables in RDS:

- **`blood_glucose`**: Glucose/CGM readings with timestamps, values (mg/dL), and metadata
  - Columns: `id`, `timestamp`, `value`, `unit`, `source`, `created_at`

- **`sleep_data`**: Sleep data with bedtime, wake time, duration, and sleep stages
  - Columns: `id`, `date`, `bedtime`, `wake_time`, `sleep_duration_minutes`, `deep_sleep_minutes`, `light_sleep_minutes`, `rem_sleep_minutes`, `sleep_efficiency`, `heart_rate_avg/min/max`, `created_at`, `updated_at`

- **`exercise_data`**: Exercise/workout data with timestamps and duration
  - Columns: `id`, `timestamp`, `duration_minutes`, `created_at`

## Running the Server

```bash
python mcp_server.py
```

The server runs as an MCP server using stdio transport, suitable for integration with Claude Desktop or other MCP clients.

## MCP Tools

The server exposes 5 MCP tools:

### Data Retrieval Tools

1. **`get_glucose_data`**
   - Retrieve glucose/blood glucose data from RDS MySQL
   - Parameters: `start_date` (optional), `end_date` (optional), `limit` (optional, default: None = all records)
   - Returns: Dictionary with `total_records`, `date_range`, `limit`, and `data` array

2. **`get_sleep_data`**
   - Retrieve sleep data from RDS MySQL
   - Parameters: `start_date` (optional), `end_date` (optional), `limit` (optional, default: None = all records)
   - Returns: Dictionary with `total_records`, `date_range`, `limit`, and `data` array

3. **`get_exercise_data`**
   - Retrieve exercise/workout data from RDS MySQL
   - Parameters: `start_date` (optional), `end_date` (optional), `limit` (optional, default: None = all records)
   - Returns: Dictionary with `total_records`, `date_range`, `limit`, and `data` array

### Analysis Tools

4. **`detect_patterns`**
   - Detect patterns in diabetes data (glucose, sleep, exercise)
   - Parameters: `start_date` (optional), `end_date` (optional), `pattern_type` (optional: "all", "glucose", "sleep", "exercise", "temporal")
   - Returns: Dictionary with detected patterns including:
     - **Glucose patterns**: Hourly averages, day-of-week averages, high/low glucose times, time-in-range by hour
     - **Sleep patterns**: Average duration/efficiency, bedtime/wake time patterns, day-of-week patterns
     - **Exercise patterns**: Frequency, timing patterns, duration patterns, day-of-week distribution

5. **`find_correlations`**
   - Find correlations between different health metrics
   - Parameters: `start_date` (optional), `end_date` (optional), `correlation_type` (optional: "all", "exercise_glucose", "sleep_glucose", "sleep_exercise")
   - Returns: Dictionary with correlation analysis including:
     - **Exercise-Glucose correlation**: Correlation between exercise duration and average/max/min glucose levels
     - **Sleep-Glucose correlation**: Correlation between sleep duration/efficiency and glucose levels
     - **Sleep-Exercise correlation**: Correlation between exercise and sleep patterns
     - All correlations include Pearson correlation coefficients and interpretations

## Testing

Run the test suite with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_mcp_tools.py -v
```

Test files:
- `tests/test_database.py`: Database connection and table existence tests
- `tests/test_mcp_tools.py`: MCP tool functionality tests

## Usage Examples

### Retrieve glucose data for a date range
```python
get_glucose_data(start_date="2025-01-01", end_date="2025-01-31", limit=100)
```

### Detect all patterns
```python
detect_patterns(start_date="2025-01-01", end_date="2025-01-31", pattern_type="all")
```

### Find exercise-glucose correlation
```python
find_correlations(start_date="2025-01-01", end_date="2025-01-31", correlation_type="exercise_glucose")
```

## Claude Desktop Configuration

To use this server with Claude Desktop, add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "diabetes-cgm": {
      "command": "/Users/namanrastogi/anaconda3/bin/python",
      "args": ["/path/to/MCP_diabetes/mcp_server.py"],
      "env": {
        "RDS_HOST": "your-rds-endpoint.region.rds.amazonaws.com",
        "RDS_PORT": "3306",
        "RDS_USER": "admin",
        "RDS_PASSWORD": "your-password",
        "RDS_DATABASE": "diabetes_cgm"
      }
    }
  }
}
```

## Dependencies

- `mcp[cli]`: Model Context Protocol server framework
- `pymysql>=1.1.0`: MySQL database connector
- `python-dotenv>=1.0.0`: Environment variable management
- `sqlalchemy>=2.0.0`: SQL toolkit and ORM
- `pytest>=7.4.0`: Testing framework
- `pytest-cov>=4.1.0`: Coverage reporting

## Notes

- All tools support optional date filtering (both `start_date` and `end_date` must be provided together)
- Default `limit` is `None` (unlimited records)
- Data is returned ordered by most recent first
- Correlation analysis requires at least 3 overlapping data points
- Pattern detection works with any amount of data available
