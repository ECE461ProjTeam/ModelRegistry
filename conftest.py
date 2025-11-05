"""
Pytest configuration for comprehensive test suite.

Configures test discovery, coverage reporting, and test execution.
"""
import pytest
import sys
import os

# Ensure src is in path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
# Ensure tests load the TestConfig in src.api.config by default so
# extensions (like SQLAlchemy) have a valid DATABASE_URI during import.
# This makes pytest collection import-safe in CI without requiring repo
# secrets. If you prefer, set DEBUG=True or DATABASE_URL in your CI
# environment instead of this change.
os.environ.setdefault("DEBUG", "True")


def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that require API access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid.lower() or "TestIntegration" in str(item.cls):
            item.add_marker(pytest.mark.integration)

        # Mark API tests
        if "api" in item.nodeid.lower() or "genai" in item.nodeid.lower():
            item.add_marker(pytest.mark.api)

        # Mark unit tests (default)
        if not any(mark.name in ["integration", "api"] for mark in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
