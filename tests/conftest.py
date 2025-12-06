"""
Pytest configuration and shared fixtures
"""
import pytest
from db_config import db_config
from sqlalchemy.orm import Session


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Provide a database session for tests.
    Automatically closes the session after each test.
    """
    session = db_config.get_session()
    yield session
    session.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Setup database connection before all tests.
    Verifies connection is available.
    """
    # Verify database connection
    assert db_config.test_connection(), "Database connection failed"
    yield
    # Cleanup if needed (currently nothing to clean up)

