"""Application configuration.

This module defines configuration classes used by the Flask app.
``Config`` is the default runtime configuration and ``TestConfig``
provides overrides intended for local testing. Values are read from
the environment when available.
"""

import os
import json
from src.logger import get_logger

logger = get_logger("config.app")

class Config:
    # Secret keys (used for signing JWTs and Flask sessions)
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")

    # Elastic Beanstalk Env has DATABASE_INFO from Secret Manager
    db_info_str = os.environ.get("DATABASE_INFO", "")
    # Load database info from environment variable string
    db_info = json.loads(db_info_str) if db_info_str else {}

    endpoint = os.environ.get("DATABASE_ENDPOINT", "")
    try:
        port = int(os.environ.get("DATABASE_PORT", 5432)) # default postgres port
    except ValueError:
        logger.warning("DATABASE_PORT is not a valid integer; using default port 5432")
        port = 5432
    db_name = os.environ.get("DATABASE_NAME")
    
    if db_info and endpoint and db_name:
        user = db_info["username"]
        psw = db_info["password"]
        
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{user}:{psw}"
            f"@{endpoint}:{port}/{db_name}"
        )
    else:
        if os.environ.get("DEBUG", "False") != "True":
            logger.warning("Database configuration incomplete (missing DATABASE_INFO, DATABASE_ENDPOINT, DATABASE_PORT, or DATABASE_NAME); using default SQLite DB.")
        # Default to local SQLite DB if no env var is set
        SQLALCHEMY_DATABASE_URI = "sqlite:///model_registry.db"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False # to suppress warnings

    # Authentication settings
    TOKEN_EXPIRE_SECONDS = int(os.environ.get("TOKEN_EXPIRE_SECONDS", 36000)) # default 10 hours
    MAX_REQUESTS_PER_TOKEN = int(os.environ.get("MAX_REQUESTS_PER_TOKEN", 1000)) # default: 1000 requests per token
    # Per OpenAPI spec this project uses X-Authorization for the token header.
    # Configure flask-jwt-extended to read the token from X-Authorization only.
    JWT_HEADER_NAME = "X-Authorization"
    JWT_HEADER_TYPE = "bearer"


class TestConfig(Config):
    """Local testing config"""
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret"
    # Use simple local SQLite DB for tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///test_model_registry.db"
    
    # Shorten token expiry and request limits for testing
    TOKEN_EXPIRE_SECONDS = int(os.environ.get("TEST_TOKEN_EXPIRE_SECONDS", 600))
    MAX_REQUESTS_PER_TOKEN = int(os.environ.get("TEST_MAX_REQUESTS_PER_TOKEN", 100))
    
    # Tests should also use X-Authorization header
    JWT_HEADER_NAME = "X-Authorization"
    JWT_HEADER_TYPE = "bearer"
