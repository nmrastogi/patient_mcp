# Tests

This directory contains pytest tests for the Diabetes MCP Server project.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_database.py
pytest tests/test_mcp_tools.py
```

### Run specific test class
```bash
pytest tests/test_database.py::TestDatabaseConnection
```

### Run specific test
```bash
pytest tests/test_mcp_tools.py::TestGlucoseDataTool::test_get_glucose_data_basic
```

### Run with coverage report
```bash
pytest --cov=mcp_server --cov=db_config --cov=models --cov-report=html
```

This will generate an HTML coverage report in `htmlcov/index.html`.

## Test Structure

### `test_database.py`
Tests for database connection and SQLAlchemy models:
- Database connection tests
- Table existence verification
- Model structure and `to_dict()` methods

### `test_mcp_tools.py`
Tests for MCP server tools:
- `get_glucose_data` tool tests
- `get_sleep_data` tool tests
- `get_exercise_data` tool tests
- Data consistency tests

## Fixtures

Shared fixtures are defined in `conftest.py`:
- `db_session`: Provides a database session for tests

## Requirements

Tests require:
- pytest >= 7.4.0
- pytest-cov >= 4.1.0
- Valid RDS database connection (configured via `.env` file)

## Writing New Tests

1. Create test files with `test_*.py` naming convention
2. Use classes with `Test*` naming for organization
3. Use `test_*` functions for individual tests
4. Use fixtures from `conftest.py` for database sessions

Example:
```python
def test_my_feature(db_session):
    """Test my feature"""
    # Your test code here
    assert True
```



