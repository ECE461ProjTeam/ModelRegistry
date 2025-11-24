"""Authentication blueprint and user management endpoints.

This module defines the `auth_bp` Blueprint which provides
endpoints for user authentication, registration and profile
management. It depends on the `User` model and the Flask
extensions configured in `extensions.py`.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt, get_jti
from .extensions import db
from .models import User, TokenUsage
from .config import Config, TestConfig
from datetime import timedelta, datetime, timezone
import os
import functools

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
        permissions=["upload", "download", "search"],
    )
    new_admin.set_password(admin_password)
    db.session.add(new_admin)
    db.session.commit()


def check_permissions(*required_permissions):
    """
    Decorator that requires the user to have ALL specified permissions. If no permissions are specified,
    only admin users are allowed.
    Admin users automatically bypass permission checks.
    Usage:
        @app.route('/some_protected_route')
        @check_permissions("permission1", "permission2")
        def protected_route():
            ...
    Returns:
        200 OK: If the user has the required permissions.
        401 Unauthorized: If the user lacks required permissions.
    """
    def decorator(fn):
        @jwt_required()
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            is_admin = claims.get("is_admin", False)
            permissions = claims.get("permissions", [])

            # If no permissions are defined, admin-only access
            if not required_permissions:
                if not is_admin:
                    return jsonify({'error': 'Admin-access only.'}), 401
                return fn(*args, **kwargs)

            # Admins automatically bypass permission checks
            if is_admin:
                return fn(*args, **kwargs)

            # Check if user has ALL required permissions
            missing = [p for p in required_permissions if p not in permissions]
            if missing:
                return jsonify({
                    'error': f'You do not have all required permissions. Missing {missing}.'
                }), 401

            return fn(*args, **kwargs)
        return wrapper
    return decorator


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
            "permissions": fetch_user.permissions
        },
        expires_delta=timedelta(seconds=config.TOKEN_EXPIRE_SECONDS)
    )

    # Get the unique identifier (JTI) of this token
    jti = get_jti(encoded_token=access_token)

    # Add a new TokenUsage record for this token
    token_record = TokenUsage(
        jti=jti,
        user_id=fetch_user.id,
        usage_count=0,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=config.TOKEN_EXPIRE_SECONDS)
    )
    db.session.add(token_record)
    db.session.commit()

    token_value = f"bearer {access_token}"

    # return jsonify({'token': token_value}), 200
    return jsonify(token_value), 200


@auth_bp.route('/register', methods=['POST'])
@check_permissions()
def register():
    """
    Register a new user. Only an admin can register new users.
    Expected JSON Request body:
    {
        "user": {
            "name": "username",
            "is_admin": true/false,
            "permissions": ["permission1", "permission2", ...]
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
    
    # Extract new user information from the request
    user = request.json.get("user")
    secret = request.json.get("secret")

    # Validate presence of required fields
    if not user or not secret or ("name" not in user) or ("password" not in secret) or ("is_admin" not in user) or ("permissions" not in user):
        return jsonify({'error': 'Missing required fields in request.'}), 400
    
    # Check if user already exists
    existing_user = User.query.filter_by(name=user["name"]).first()
    if existing_user:
        return jsonify({'error': 'User already exists.'}), 400
    
    # Ensure permissions is not empty and is a list
    if not isinstance(user["permissions"], list):
        return jsonify({'error': 'Permissions must be a list.'}), 400
    
    if not user["is_admin"] and len(user["permissions"]) == 0:
        return jsonify({'error': 'User must have at least one permission.'}), 400

    # Create new user
    new_user = User(name=user["name"], is_admin=user["is_admin"], permissions=user["permissions"])
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
        500 Internal Server Error: If deletion fails due to server error.
    """
    # Ensure request is JSON and extract payload first
    if not request or not request.is_json:
        return jsonify({'error': 'Invalid request format.'}), 400

    # Extract user information from the request
    user = request.json.get("user")

    # Validate presence of required fields
    if not user or "name" not in user:
        return jsonify({'error': 'Missing required fields in request.'}), 400

    # Check if current user is authorized to delete the profile
    request_user = get_jwt_identity()
    # Verify admin permissions
    claims = get_jwt()  # dict with additional_claims
    is_admin = claims.get("is_admin", False)

    # Allow deletion if the requester is the owner OR an admin.
    # Deny only when the requester is neither the owner nor an admin.
    if request_user != user.get("name") and not is_admin:
        return jsonify({'error': 'Not authorized to delete this profile.'}), 403
    
    # Fetch user to be deleted
    fetch_user = User.query.filter_by(name=user["name"]).first()
    if not fetch_user:
        return jsonify({'error': 'User not found.'}), 400
    
    # Delete any token usage records for this user
    try:
        # Remove all TokenUsage records associated with this user.
        db.session.query(TokenUsage).filter_by(user_id=fetch_user.id).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed deleting token usage records for user %s", fetch_user.name)
        return jsonify({'error': 'Failed to delete user tokens.'}), 500

    # Delete user profile
    try:
        db.session.delete(fetch_user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed deleting user profile %s", fetch_user.name)
        return jsonify({'error': 'Failed to delete user profile.'}), 500
    
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

    # Include request_count for the current token (if tracked)
    claims = get_jwt()
    jti = claims.get('jti')
    request_count = 0
    if jti:
        token_record = TokenUsage.query.filter_by(jti=jti).first()
        if token_record:
            request_count = token_record.usage_count

    user_profile = {
        "name": fetch_user.name,
        "is_admin": fetch_user.is_admin,
        "permissions": fetch_user.permissions,
        "request_count": request_count,
    }

    return jsonify({'profile': user_profile}), 200


@auth_bp.route('/users', methods=['GET'])
@check_permissions()
def get_users():
    """Admin is permitted to view list of all users"""    
    users = User.query.all()
    user_list = [{"name": user.name, "is_admin": user.is_admin} for user in users]
    
    return jsonify({'users': user_list}), 200
    
