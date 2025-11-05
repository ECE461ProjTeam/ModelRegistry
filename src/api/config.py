"""Application configuration.

This module defines configuration classes used by the Flask app.
``Config`` is the default runtime configuration and ``TestConfig``
provides overrides intended for local testing. Values are read from
the environment when available.
"""

import os

class Config:
    # Secret keys (used for signing JWTs and Flask sessions)
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") 
    SQLALCHEMY_TRACK_MODIFICATIONS = False # to suppress warnings

    # Authentication settings
    TOKEN_EXPIRE_SECONDS = os.environ.get("TOKEN_EXPIRE_SECONDS")
    MAX_REQUESTS_PER_TOKEN = os.environ.get("MAX_REQUESTS_PER_TOKEN")


class TestConfig(Config):
    """Local testing config"""
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret"
    # Use simple local SQLite DB for tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///test_model_registry.db"
    
    # Shorten token expiry and request limits for testing
    TOKEN_EXPIRE_SECONDS = os.environ.get("TEST_TOKEN_EXPIRE_SECONDS", 600)
    MAX_REQUESTS_PER_TOKEN = os.environ.get("TEST_MAX_REQUESTS_PER_TOKEN", 10)