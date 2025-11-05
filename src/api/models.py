"""Database models for the API.

This module defines SQLAlchemy models used by the API (currently a
``User`` model). Models import the shared ``db`` instance from
``extensions.py`` so migrations and the application context can bind
to a database when the Flask app is initialized.
"""

from .extensions import db
from datetime import datetime, timezone
from flask_bcrypt import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(200), nullable=False)  # increased length for hashed passwords
    is_admin = db.Column(db.Boolean, default=False)
    # permissions = db.Column(db.JSON, nullable=False, default=list)
    request_count = db.Column(db.Integer, default=0)

    def set_password(self, plain_password):
        """Hashes the password using bcrypt before storing it."""
        self.password = generate_password_hash(plain_password).decode("utf-8")

    def check_password(self, plain_password):
        """Checks a plain-text password against the stored bcrypt hash."""
        return check_password_hash(self.password, plain_password)
    
