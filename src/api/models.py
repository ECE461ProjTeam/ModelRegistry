"""Database models for the API.

This module defines SQLAlchemy models used by the API (currently a
``User`` model). Models import the shared ``db`` instance from
``extensions.py`` so migrations and the application context can bind
to a database when the Flask app is initialized.
"""

from .extensions import db
from flask_bcrypt import generate_password_hash, check_password_hash
import uuid
from .config import TestConfig, Config
import os
from datetime import datetime, timezone

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(200), nullable=False)  # increased length for hashed passwords
    is_admin = db.Column(db.Boolean, default=False)
    permissions = db.Column(db.JSON, nullable=False, default=list)

    def set_password(self, plain_password):
        """Hashes the password using bcrypt before storing it."""
        self.password = generate_password_hash(plain_password).decode("utf-8")

    def check_password(self, plain_password):
        """Checks a plain-text password against the stored bcrypt hash."""
        return check_password_hash(self.password, plain_password)
    

class TokenUsage(db.Model):
    """Tracks usage-based expiration for JWT tokens."""
    jti = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    usage_count = db.Column(db.Integer, default=0, nullable=False)
    # When the token should be considered expired (time-based)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User", backref=db.backref("tokens", lazy=True))

    def increment_usage(self):
        """Increment usage counter by one."""
        self.usage_count += 1
        db.session.commit()

    @property
    def is_expired(self):
        """Check if token exceeded allowed requests."""
        # Check request-count based expiration
        if os.environ.get("DEBUG") == "True":
            MAX_REQUESTS = TestConfig.MAX_REQUESTS_PER_TOKEN
        else:
            MAX_REQUESTS = Config.MAX_REQUESTS_PER_TOKEN

        # Check time-based expiration as well
        now = datetime.now(timezone.utc)
        expires = self.expires_at

        # If expires_at is stored as a naive datetime (older records),
        # assume it's UTC and convert to an aware datetime to allow comparison.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
            # Persist the normalized value so future checks won't hit this branch.
            try:
                self.expires_at = expires
                db.session.add(self)
                db.session.commit()
            except Exception:
                db.session.rollback()

        time_expired = now >= expires
        usage_expired = self.usage_count >= MAX_REQUESTS

        return time_expired or usage_expired