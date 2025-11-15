"""Application configuration.

This module defines configuration classes used by the Flask app.
``Config`` is the default runtime configuration and ``TestConfig``
provides overrides intended for local testing. Values are read from
the environment when available.
"""

import os
import json

class Config:
    # Secret keys (used for signing JWTs and Flask sessions)
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")

    # Elastic Beanstalk Env has DATABASE_INFO from Secret Manager
    db_info_str = os.environ.get("DATABASE_INFO", "")
    # Load database info from environment variable string
    db_info = json.loads(db_info_str) if db_info_str else {}

    if db_info == {}:
        # Error if no DB info found
        raise ValueError("Database configuration not found in environment.")
    
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{db_info['username']}:{db_info['password']}"
        f"@{db_info['host']}:{db_info['port']}/{db_info['dbname']}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False # to suppress warnings

    # Authentication settings
    TOKEN_EXPIRE_SECONDS = os.environ.get("TOKEN_EXPIRE_SECONDS")
    MAX_REQUESTS_PER_TOKEN = os.environ.get("MAX_REQUESTS_PER_TOKEN")
    # Per OpenAPI spec this project uses X-Authorization for the token header.
    # Configure flask-jwt-extended to read the token from X-Authorization only.
    JWT_HEADER_NAME = "X-Authorization"
    JWT_HEADER_TYPE = "Bearer"


class TestConfig(Config):
    """Local testing config"""
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret"
    # Use simple local SQLite DB for tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///test_model_registry.db"
    
    # Shorten token expiry and request limits for testing
    TOKEN_EXPIRE_SECONDS = os.environ.get("TEST_TOKEN_EXPIRE_SECONDS", 600)
    MAX_REQUESTS_PER_TOKEN = os.environ.get("TEST_MAX_REQUESTS_PER_TOKEN", 10)
    
    # Tests should also use X-Authorization header
    JWT_HEADER_NAME = "X-Authorization"
    JWT_HEADER_TYPE = "Bearer"