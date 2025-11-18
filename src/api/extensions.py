"""Flask extension instances and initialization helper.

This module creates extension instances (SQLAlchemy, JWTManager and
Bcrypt) so they can be imported and used across the application. 
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import os

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()

def init_extensions(app):
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # If there is an env variable ALLOWED_ORIGINS, use it to set CORS origins, else default to localhost:5173
    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
    
    CORS(app, resources={r"/*": {"origins": allowed_origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "X-Authorization"])