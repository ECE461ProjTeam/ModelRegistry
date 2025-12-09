"""Database models for the API.

This module defines SQLAlchemy models used by the API (currently a
``User`` model). Models import the shared ``db`` instance from
``extensions.py`` so migrations and the application context can bind
to a database when the Flask app is initialized.
"""

import zipfile
from src.api.s3 import get_download_link, upload_file_to_s3
from src.metrics.data_fetcher.huggingface import download_hf_model
from .extensions import db
from flask_bcrypt import generate_password_hash, check_password_hash
import uuid
from .config import TestConfig, Config
import os
from datetime import datetime, timezone
from src.logger import get_logger
from ..url_parsers.url_type_handler import handle_url
from ..cli.validate import validate_ndjson
import requests

logger = get_logger("api.models")

CHECK_INGESTIBILITY = int(os.environ.get("CHECK_INGESTIBILITY", 0))

# Check request-count based expiration number based on config
if os.environ.get("DEBUG") == "True":
    MAX_REQUESTS = int(TestConfig.MAX_REQUESTS_PER_TOKEN)
else:
    MAX_REQUESTS = int(Config.MAX_REQUESTS_PER_TOKEN)
    
class Artifact(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    download_url = db.Column(db.String(300), nullable=True)
    name = db.Column(db.String(150), nullable=True)
    url = db.Column(db.String(300), nullable=False)
    code_url = db.Column(db.String(300), nullable=True)
    dataset_url = db.Column(db.String(300), nullable=True)
    ndjson = db.Column(db.JSON, nullable=True)
    cost = db.Column(db.Float, nullable=True)  # in MB
    ingestible = db.Column(db.Boolean, default=False)
    readme = db.Column(db.Text, nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ndjson = {}
        
        self.ingestible = True  # Default to True; may be updated below
        
        if self.type == "model":
            self.rate()
            if CHECK_INGESTIBILITY and not self.check_ingestible():
                logger.warning(f"Artifact {self.id} is not ingestible; skipping upload to S3.")
                self.ingestible = False
                return
        
        try:
            self.send_to_bucket()
        except Exception as e:
            logger.error(f"Error sending artifact {self.id} to bucket: {e}")
                
        
    @staticmethod
    def make_id() -> int:
        return int(uuid.uuid4().int % 1e11)
    
    def rate(self) -> bool:
        if self.ndjson != {}:
            logger.info("Model already rated, skipping re-rating.")
            return True
        
        logger.info(f"Rating model artifact {self.id} with name {self.name}")
        try:
            raw_ndjson = handle_url({0: [self.code_url, self.dataset_url, self.url]})[0]
        except Exception as e:
            logger.error(f"Error handling URL for rating: {e}")
            return False
        if(validate_ndjson(raw_ndjson)):
            self.ndjson = raw_ndjson
            self.ndjson.update({'name': self.name, 'category': self.type})
        
        logger.info(f"Completed rating for model artifact {self.id} with name {self.name}")
        return True
    
    def check_ingestible(self) -> bool:
        if self.ndjson == {}:
            return False
              
        for key in self.ndjson:
            # Skip non-metric fields
            if not key.endswith("_latency") and key not in ["name", "category", "lineage"]:
                if isinstance(self.ndjson[key], dict):
                    for subkey in self.ndjson[key]:
                        if self.ndjson[key][subkey] < 0.5:
                            return False
                if self.ndjson[key] < 0.5:
                    return False
        return True
    
    def send_to_bucket(self):
        """Download model files and store them in S3."""
        if self.type != "model":
            logger.info(f"Artifact {self.id} is of type {self.type}; skipping file download")
            local_dir = f"./hf_cache/{self.type}--{self.name}"
            os.makedirs(local_dir, exist_ok=True)
            logger.info(f"Creating placeholder files for {self.type} artifact {self.id}")
            with open(f"{local_dir}/{self.name}_metadata.txt", 'w+') as f:
                f.write("Name: " + self.name + "\n" + "URL: " + self.url + "\n" + "Type: " + self.type + "\n")
        
        else:
            logger.info(f"Downloading model files for artifact {self.id} from {self.url}")
            local_dir = download_hf_model(self.url, cache_dir="./hf_cache")

            if local_dir is None:
                logger.error(f"Failed to download model files for artifact {self.id} from {self.url}")
                return
            logger.info(f"Downloaded model files to {local_dir}")

        try:
            with open(f'{local_dir}/README.md', 'r') as f:
                self.readme = f.read()
                logger.info(f"Read README.md for artifact {self.id}")
        except Exception as e:
            logger.error(f"Could not read README.md for artifact {self.id}: {e}")
            self.readme = ""

        try:
            self.zip_model(local_dir)
            logger.info(f"Created zip file {self.id}.zip (size: {self.cost} MB)")
            logger.info(f"Uploading zip file {self.id}.zip to S3")
            success = upload_file_to_s3(f"{local_dir}/{self.id}.zip", f"{self.id}.zip")
            if not success:
                logger.error(f"Failed to upload {self.id}.zip to S3")
                raise RuntimeError(f"Failed to upload {self.id}.zip to S3")
        except Exception as e:
            logger.error(f"Error during zipping or uploading to S3: {e}")
            os.remove(f"{local_dir}/{self.id}.zip")
            return
        
        logger.info(f"Uploaded zip file {self.id}.zip to S3")
        os.remove(f"{local_dir}/{self.id}.zip")

        self.download_url = get_download_link(self.id)
    
    def zip_model(self, local_dir):
        zout = zipfile.ZipFile(f"{local_dir}/{self.id}.zip", "w")
        for root, _, files in os.walk(local_dir):
            for file in files:
                if file == f"{self.id}.zip":
                    continue  # Skip adding the zip file itself
                local_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_file_path, local_dir)
                logger.debug(f"Adding {local_file_path} as {rel_path} to zip")
                zout.write(local_file_path, arcname=rel_path)
        zout.close()
                    
        self.cost = os.path.getsize(f"{local_dir}/{self.id}.zip") / (1024 * 1024)  # size in MB
        
    @staticmethod
    def is_valid_hf_url(url: str) -> bool:
        """Check if the provided URL is a valid Hugging Face model URL."""
        return url.startswith("https://huggingface.co/") or url.startswith("http://huggingface.co/")
    
    @staticmethod
    def is_valid_git_url(url: str) -> bool:
        """Check if the provided URL is a valid Git repository URL."""
        return url.startswith("git://") or url.startswith("https://github.com/") or url.startswith("http://github.com/") \
                or url.startswith("https://gitlab.com/") or url.startswith("http://gitlab.com/")
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if the provided URL is a valid HTTP/HTTPS URL."""
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        try:
            response = requests.get(url)
            return response.status_code != 404
        except requests.exceptions.RequestException:
            return False

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