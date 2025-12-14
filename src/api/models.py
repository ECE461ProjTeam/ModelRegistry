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
from sqlalchemy.orm.attributes import flag_modified
import requests
from src.metrics.data_fetcher.llm import get_genai_dataset_code_links
from src.metrics.data_fetcher.huggingface import get_huggingface_file


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
    sensitive = db.Column(db.Boolean, default=False)
    download_history = db.Column(db.JSON, nullable=True, default=None)
    js_program = db.Column(db.Text, nullable=True)
    uploader_name = db.Column(db.String(150), nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ndjson = {}
        
        if self.sensitive:
            self.download_history = list()
        
        self.ingestible = True  # Default to True; may be updated below
        
        if self.type == "model":
            self.rate()
            if CHECK_INGESTIBILITY and not self.check_ingestible():
                logger.warning(f"Artifact {self.id} is not ingestible; skipping upload to S3.")
                self.ingestible = False
                return
        
        # try:
        #     self.send_to_bucket()
        # except Exception as e:
        #     logger.error(f"Error sending artifact {self.id} to bucket: {e}")
                
        
    @staticmethod
    def make_id() -> int:
        return int(uuid.uuid4().int % 1e11)
    
    def rate(self) -> bool:
        """Rate the model artifact and compute tree_score.
        
        Two scenarios:
        1. Initial rating (ndjson is empty): Compute all metrics, port net_score to tree_score
        2. Re-rating (ndjson is populated): Recompute tree_score from lineage, recalculate net_score
        """
        is_initial_rating = (self.ndjson == {} or self.ndjson is None)
        
        if is_initial_rating:
            logger.info(f"Initial rating for model artifact {self.id} with name {self.name}")
            
            # Get README for LLM extraction
            readme_path = get_huggingface_file(self.url)
            with open(readme_path, 'r') as f:
                self.readme = f.read()
            
            # Extract code and dataset URLs
            self.extract_code_dataset_urls_from_llm()
            
            # Compute all metrics (including initial tree_score via metrics)
            try:
                raw_ndjson = handle_url({0: [self.code_url, self.dataset_url, self.url]})[0]
            except Exception as e:
                logger.error(f"Error handling URL for rating: {e}")
                return False
            
            if validate_ndjson(raw_ndjson):
                self.ndjson = raw_ndjson
                self.ndjson.update({'name': self.name, 'category': self.type})
                
                # For initial rating, tree_score is already set by tree_score.py metric
                # It uses net_score as the initial tree_score value
                logger.info(f"Initial rating complete. tree_score: {self.ndjson.get('tree_score', 'N/A')}, net_score: {self.ndjson.get('net_score', 'N/A')}")
            else:
                logger.error(f"Invalid ndjson generated for artifact {self.id}")
                return False
                
        else:
            # Re-rating scenario: recompute tree_score from lineage
            logger.info(f"Re-rating model artifact {self.id} with name {self.name}")
            
            # Check if lineage data exists
            lineage_data = self.ndjson.get('lineage', {})
            if not lineage_data:
                logger.warning(f"No lineage data found for artifact {self.id}, cannot recompute tree_score")
                return True  # Return success but don't update tree_score
            
            # Compute tree_score from lineage
            try:
                from src.api.lineage import compute_tree_score_for_model
                
                result = compute_tree_score_for_model(lineage_data, self.id, db.session)
                new_tree_score = result["tree_score"]
                
                logger.info(f"Recomputed tree_score: {new_tree_score:.3f} from {result['model_count']} related models")
                
                # Update tree_score in ndjson
                old_tree_score = self.ndjson.get('tree_score', 0.0)
                self.ndjson['tree_score'] = new_tree_score
                
                # Recalculate net_score since tree_score changed
                old_net_score = self.ndjson.get('net_score', 0.0)
                self.recalculate_net_score()
                new_net_score = self.ndjson.get('net_score', 0.0)
                
                logger.info(f"Updated scores - tree_score: {old_tree_score:.3f} -> {new_tree_score:.3f}, net_score: {old_net_score:.3f} -> {new_net_score:.3f}")
                
                # CRITICAL: Mark ndjson as modified so SQLAlchemy knows to UPDATE it
                # Without this, in-place dict modifications aren't detected
                flag_modified(self, 'ndjson')
                
            except Exception as e:
                logger.error(f"Error recomputing tree_score for artifact {self.id}: {e}")
                return False
        
        logger.info(f"Completed rating for model artifact {self.id} with name {self.name}")
        return True
    
    def recalculate_net_score(self):
        """Recalculate net_score based on current metric values in ndjson.
        
        net_score is typically calculated as a weighted average of other metrics.
        This method recomputes it after tree_score has been updated.
        """
        if not self.ndjson:
            logger.warning(f"Cannot recalculate net_score for artifact {self.id}: ndjson is empty")
            return
        
        # Define which metrics contribute to net_score
        # Excluding: name, category, lineage, *_latency fields, net_score itself
        metric_keys = []
        for key in self.ndjson:
            if (not key.endswith("_latency") and 
                key not in ["name", "category", "lineage", "net_score"]):
                metric_keys.append(key)
        
        if not metric_keys:
            logger.warning(f"No metrics found to calculate net_score for artifact {self.id}")
            return
        
        # Calculate net_score as average of all metric scores
        total = 0.0
        count = 0
        
        for key in metric_keys:
            value = self.ndjson[key]
            if isinstance(value, dict):
                # If metric is a dict, average its sub-values
                sub_values = [v for v in value.values() if isinstance(v, (int, float))]
                if sub_values:
                    total += sum(sub_values) / len(sub_values)
                    count += 1
            elif isinstance(value, (int, float)):
                total += value
                count += 1
        
        if count > 0:
            new_net_score = total / count
            self.ndjson['net_score'] = new_net_score
            logger.debug(f"Recalculated net_score for artifact {self.id}: {new_net_score:.3f} (average of {count} metrics)")
        else:
            logger.warning(f"No valid metric values found to calculate net_score for artifact {self.id}")
    
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
                elif self.ndjson[key] < 0.5:
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
        
    def extract_code_dataset_urls_from_llm(self):
        from huggingface_hub import HfApi, model_info
        from src.metrics.data_fetcher.utils import extract_hf_model_id
        model_id = extract_hf_model_id(self.url)
        if not model_id:
            return {}

        info = model_info(model_id)
        data = {
            "license": None,
            "tags": getattr(info, "tags", []) or [],
            "downloads": getattr(info, "downloads", 0) or 0,
            "pipeline_tag": getattr(info, "pipeline_tag", None),
            "model_id": getattr(info, "modelId", model_id),
            "sha": getattr(info, "sha", None),
            "card_data": getattr(info, "cardData", {}) or {},
            "config": getattr(info, "config", {}) or {},
        }
        datasets = data["card_data"]     
        
        dataset_response = get_genai_dataset_code_links(self.url, 
            f"Given the following huggingface model URL, one url for the \
                huggingface page of the dataset it was trained on\
                If it is not listed, return the word None_Found. \
                For Datasets, look for these specifically, pick ONLY ONE: {datasets} \
                As an example, if the dataset is 'bookcorpus', the link must be EXACTLY 'https://huggingface.co/datasets/bookcorpus/bookcorpus' \
                and for 'wikipedia', the link must be EXACTLY 'https://huggingface.co/datasets/legacy-datasets/wikipedia'. \
                Make sure the dataset links actually go to a dataset. \
                Respond ONLY with the link. Do not add any justification, I just want the link.").get("response")
        code_response = get_genai_dataset_code_links(self.url,
            f"Given the following huggingface model readme, return one url for its \
                github code repository. If it is not listed, return the word None_Found. \
                Make sure the code link actually goes to a code repository. \
                Ensure the link does not end with .html \
                Respond with ONLY the link. No other text AT ALL. Do not add any justification, I just want the link. \
                {self.readme}    ").get("response")
        
        dataset = dataset_response.strip() if dataset_response else None
        code = code_response.strip() if code_response else None
        if code != "None_Found" and code is not None:
            if "/tree/" in code:
                self.code_url = code.split("/tree/")[0]
            else:
                self.code_url = code
            
        if dataset != "None_Found" and dataset is not None:
            self.dataset_url = dataset
                
        logger.debug(f"Extracted code URL: {self.code_url}, dataset URL: {self.dataset_url} from LLM response.")
        
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