"""Authentication blueprint and user management endpoints.

This module defines the `auth_bp` Blueprint which provides
endpoints for user authentication, registration and profile
management. It depends on the `User` model and the Flask
extensions configured in `extensions.py`.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from .extensions import db
from .models import User
from .config import Config, TestConfig
from sqlalchemy import update
from datetime import timedelta
import os


auth_bp = Blueprint("auth_bp", __name__)
config = TestConfig if os.environ.get("DEBUG") == "True" else Config
from src.logger import get_logger
logger = get_logger("api.auth")


def create_default_admin():
    """Create a default admin user if none exists."""
    admin_name = os.environ.get("DEFAULT_USER")
    admin_password = os.environ.get("DEFAULT_PASSWORD")

    # Check if an admin already exists
    admin_user = User.query.filter_by(is_admin=True).first()
    if admin_user:
        return

    # Create new admin user
    new_admin = User(
        name=admin_name,
        is_admin=True,
        # permissions=["upload", "download", "search"],
    )
    new_admin.set_password(admin_password)
    db.session.add(new_admin)
    db.session.commit()


def increment_request_count(user_name):
    """Atomically increment the request_count for any supported DB (Sqlite for local, Postgres for production)."""
    try:
        # Detect DB dialect
        bind = db.session.get_bind()
        if not bind:
            return False
        dialect = bind.dialect.name
        
        if dialect == "postgresql":
            stmt = (
                update(User)
                .where(User.name == user_name)
                .values(request_count=User.request_count + 1)
                .returning(User.request_count)
            )
            result = db.session.execute(stmt)
            new_count = result.scalar_one_or_none()

        else:
            # SQLite fallback (no RETURNING)
            user = User.query.filter_by(name=user_name).first()
            if not user:
                return False
            user.request_count = user.request_count + 1
            db.session.commit()
            new_count = user.request_count
    except Exception as e:
        db.session.rollback()
        return False

    if new_count is None:
        return False
    return new_count <= config.MAX_REQUESTS_PER_USER


@auth_bp.route('/authenticate', methods=['PUT'])
def authenticate():
    """
    Authenticate user's credentials and provide an authentication token.
    Expected JSON Request body:
    {
        "user": {
            "name": "username",
            "is_admin": true/false
        },
        "secret": {
            "password": "user's password"
        }
    }

    Returns:
        200 OK: If authentication is successful. Also return authentication token for future requests.
        400 Bad Request: If any required field is missing or invalid.
        401 Unauthorized: If authentication fails due to invalid credentials.
    """
    # Check if request is JSON
    if not request or not request.is_json:
        return jsonify({'error': 'Invalid request format.'}), 400

    # Extract user and secret information from the request
    user = request.json.get("user")
    secret = request.json.get("secret")

    # Validate presence of required fields
    if not user or not secret or "name" not in user or "password" not in secret:
        return jsonify({'error': 'Missing required fields in request.'}), 400
    
    # Fetch user from the database
    fetch_user = User.query.filter_by(name=user["name"]).first()
    if not fetch_user:
        return jsonify({'error': 'The user or password is invalid'}), 401
    
    # Verify password
    if not fetch_user.check_password(secret["password"]):
        return jsonify({'error': 'Invalid credentials.'}), 401

    # Create JWT token
    access_token = create_access_token(
        identity=fetch_user.name,
        additional_claims={
            "is_admin": fetch_user.is_admin,
        },
        expires_delta=timedelta(seconds=config.TOKEN_EXPIRE_SECONDS)
    )
    # Whenever we issue a new token, reset the request counter and update
    # the last_reset timestamp so the user starts with a fresh quota.
    # (Token expiry itself is handled by Flask-JWT-Extended via the
    # `expires_delta` above.)
    fetch_user.request_count = 0
    db.session.commit()

    return jsonify({'token': access_token}), 200


@auth_bp.route('/register', methods=['POST'])
@jwt_required()
def register():
    """
    Register a new user. Only an admin can register new users.
    Expected JSON Request body:
    {
        "user": {
            "name": "username",
            "is_admin": true/false
        },
        "secret": {
            "password": "user's password"
        }
    }
    Returns:
        201 Created: If user registration is successful.
        400 Bad Request: If any required field is missing or invalid.
        403 Forbidden: If the current user is not an admin.
    """
    # Check if request is JSON
    if not request or not request.is_json:
        return jsonify({'error': 'Invalid request format.'}), 400

     # Verify admin permissions
    claims = get_jwt()  # dict with additional_claims
    is_admin = claims.get("is_admin", False)

    if not is_admin:
        return jsonify({'error': 'Admin privileges required to register new users.'}), 403
    
    # Extract new user information from the request
    user = request.json.get("user")
    secret = request.json.get("secret")

    # Validate presence of required fields
    if not user or not secret or "name" not in user or "password" not in secret or "is_admin" not in user:
        return jsonify({'error': 'Missing required fields in request.'}), 400
    
    # Check if user already exists
    existing_user = User.query.filter_by(name=user["name"]).first()
    if existing_user:
        return jsonify({'error': 'User already exists.'}), 400
    
    # Create new user
    new_user = User(name=user["name"], is_admin=user["is_admin"])
    new_user.set_password(secret["password"])
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'User registered successfully.'}), 201


@auth_bp.route('/profile', methods=['DELETE'])
@jwt_required()
def delete_profile():
    """
    Delete the profile of the current user (if user). 
    Delete the profile of any user (if admin). 
    
    Expected JSON Request body:
    {
        "user": {
            "name": "username"
        }
    }
    Returns:
        200 OK: If profile deletion is successful.
        400 Bad Request: If any required field is missing or invalid.
        403 Forbidden: If the current user is not authorized to delete the specified profile.
    """
    # Check if request is JSON
    if not request or not request.is_json:
        return jsonify({'error': 'Invalid request format.'}), 400

    # Extract user information from the request
    user = request.json.get("user")

    # Validate presence of required fields
    if not user or "name" not in user:
        return jsonify({'error': 'Missing required fields in request.'}), 400
    
    # Fetch user to be deleted
    fetch_user = User.query.filter_by(name=user["name"]).first()
    if not fetch_user:
        return jsonify({'error': 'User not found.'}), 400
    
    # Check if current user is authorized to delete the profile
    request_user = get_jwt_identity()
    
    # Verify admin permissions
    claims = get_jwt()  # dict with additional_claims
    is_admin = claims.get("is_admin", False)

    # Allow deletion if the requester is the owner OR an admin.
    # Deny only when the requester is neither the owner nor an admin.
    if request_user != user.get("name") and not is_admin:
        return jsonify({'error': 'Not authorized to delete this profile.'}), 403
    
    # Delete user profile
    db.session.delete(fetch_user)
    db.session.commit()
    
    return jsonify({'message': 'User profile deleted successfully.'}), 200


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """
    Get the profile of the current user.
    
    Returns:
        200 OK: If profile retrieval is successful.
        400 Bad Request: If the user is not found.
    """
    current_user = get_jwt_identity()
    fetch_user = User.query.filter_by(name=current_user).first()
    if not fetch_user:
        return jsonify({'message': 'User not found.'}), 400
    
    user_profile = {
        "name": fetch_user.name,
        "is_admin": fetch_user.is_admin,
        "request_count": fetch_user.request_count,
    }
    
    return jsonify({'profile': user_profile}), 200