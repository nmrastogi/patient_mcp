"""
Pytest tests for MCP server tools
"""
import pytest
from mcp_server import get_glucose_data, get_sleep_data, get_exercise_data
from datetime import datetime, timedelta


class TestGlucoseDataTool:
    """Test get_glucose_data tool"""
    
    def test_get_glucose_data_basic(self):
        """Test basic glucose data retrieval"""
        result = get_glucose_data(limit=10)
        
        assert 'table' in result
        assert result['table'] == 'blood_glucose'
        assert 'total_records' in result
        assert 'data' in result
        assert isinstance(result['data'], list)
        assert len(result['data']) <= 10
    
    def test_get_glucose_data_with_dates(self):
        """Test glucose data retrieval with date range"""
        # Get data from last 7 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        result = get_glucose_data(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            limit=100
        )
        
        assert 'table' in result
        assert 'total_records' in result
        assert 'date_range' in result
        assert 'data' in result
    
    def test_get_glucose_data_invalid_date_format(self):
        """Test glucose data with invalid date format"""
        result = get_glucose_data(
            start_date='invalid-date',
            end_date='2025-01-01'
        )
        
        assert 'error' in result
        assert 'Invalid date format' in result['error']


class TestSleepDataTool:
    """Test get_sleep_data tool"""
    
    def test_get_sleep_data_basic(self):
        """Test basic sleep data retrieval"""
        result = get_sleep_data(limit=10)
        
        assert 'table' in result
        assert result['table'] == 'sleep_data'
        assert 'total_records' in result
        assert 'data' in result
        assert isinstance(result['data'], list)
        assert len(result['data']) <= 10
    
    def test_get_sleep_data_with_dates(self):
        """Test sleep data retrieval with date range"""
        # Get data from last 30 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        result = get_sleep_data(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            limit=100
        )
        
        assert 'table' in result
        assert 'total_records' in result
        assert 'date_range' in result
        assert 'data' in result
    
    def test_get_sleep_data_invalid_date_format(self):
        """Test sleep data with invalid date format"""
        result = get_sleep_data(
            start_date='invalid-date',
            end_date='2025-01-01'
        )
        
        assert 'error' in result
        assert 'Invalid date format' in result['error']


class TestExerciseDataTool:
    """Test get_exercise_data tool"""
    
    def test_get_exercise_data_basic(self):
        """Test basic exercise data retrieval"""
        result = get_exercise_data(limit=10)
        
        assert 'table' in result
        assert result['table'] == 'exercise_data'
        assert 'total_records' in result
        assert 'data' in result
        assert isinstance(result['data'], list)
        assert len(result['data']) <= 10
    
    def test_get_exercise_data_with_dates(self):
        """Test exercise data retrieval with date range"""
        # Get data from last 7 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        result = get_exercise_data(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            limit=100
        )
        
        assert 'table' in result
        assert 'total_records' in result
        assert 'date_range' in result
        assert 'data' in result
    
    def test_get_exercise_data_invalid_date_format(self):
        """Test exercise data with invalid date format"""
        result = get_exercise_data(
            start_date='invalid-date',
            end_date='2025-01-01'
        )
        
        assert 'error' in result
        assert 'Invalid date format' in result['error']


class TestDataConsistency:
    """Test data consistency across tools"""
    
    def test_all_tools_return_data(self):
        """Test that all three tools return data"""
        glucose = get_glucose_data(limit=1)
        sleep = get_sleep_data(limit=1)
        exercise = get_exercise_data(limit=1)
        
        assert glucose.get('total_records', 0) > 0
        assert sleep.get('total_records', 0) > 0
        assert exercise.get('total_records', 0) > 0
    
    def test_data_structure_consistency(self):
        """Test that all tools return consistent data structures"""
        glucose = get_glucose_data(limit=1)
        sleep = get_sleep_data(limit=1)
        exercise = get_exercise_data(limit=1)
        
        # All should have same top-level keys
        required_keys = ['table', 'total_records', 'data']
        for result in [glucose, sleep, exercise]:
            for key in required_keys:
                assert key in result, f"{result.get('table')} missing key: {key}"


