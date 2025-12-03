from flask import Blueprint, request, jsonify
from .extensions import db
from .config import Config, TestConfig
from .models import Artifact
from .auth import check_permissions
from src.logger import get_logger
from src.metrics.data_fetcher.utils import extract_repo_info
from src.metrics.impl.license_compliance import LicenseComplianceMetric
import os
import re
import requests

license_check_bp = Blueprint("license_check_bp", __name__)
config = TestConfig if os.environ.get("DEBUG") == "True" else Config
logger = get_logger("api.license_check")


def normalize_license(license_str):
    """Normalize license string for comparison."""
    if not license_str:
        return None
    return license_str.lower().strip()


def validate_github_url(github_url):
    """Validate GitHub URL format and return True if valid."""
    if not github_url or not isinstance(github_url, str):
        return False
    
    github_pattern = r'^https?://github\.com/[\w\.-]+/[\w\.-]+/?.*$'
    if not re.match(github_pattern, github_url):
        return False
    
    owner, repo = extract_repo_info(github_url)
    return owner is not None and repo is not None


def fetch_github_license(github_url):
    """
    Fetch license from GitHub API.
    Returns (license_spdx_id or None, status_code: int)
    status_code: 200 (success), 404 (not found), 502 (other error)
    """
    owner, repo = extract_repo_info(github_url)
    if not owner or not repo:
        return None, 404
    
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}"} if token else {}
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            return None, 404
        
        if not response.ok:
            return None, 502
        
        data = response.json()
        license_info = data.get("license")
        
        if not license_info:
            return None, 200
        
        license_spdx = license_info.get("spdx_id")
        if not license_spdx or license_spdx == "NOASSERTION":
            return None, 200
        
        return license_spdx, 200
        
    except Exception as e:
        logger.error(f"Error fetching GitHub license: {e}")
        return None, 502


@license_check_bp.route('/artifact/model/<int:model_id>/license-check', methods=['POST'])
@check_permissions('search')
def license_check(model_id):
    """
    Check license compatibility between a GitHub repository and an uploaded model.
    
    Args:
        model_id: The ID of the model artifact to check against
        
    Request Body:
        {
            "github_url": "https://github.com/owner/repo"
        }
        
    Returns:
        200: Returns boolean (true/false) indicating compatibility
        400: Malformed request or invalid GitHub URL
        403: Authentication failed (handled by decorators)
        404: Model not found or GitHub repository not found
        502: External license information could not be retrieved
    """
    try:
        # Authentication is handled by decorators; see version control for previous manual approaches.
        data = request.get_json()
        github_url = (data or {}).get('github_url', '').strip()

        if not validate_github_url(github_url):
            return jsonify({'error': 'The license check request is malformed or references an unsupported usage context.'}), 400
        
        logger.info(f"License check requested for model {model_id} against {github_url}")
        
        # Find the model artifact
        try:
            model = Artifact.query.filter_by(id=model_id).first()
        except Exception as e:
            logger.error(f"Database error when querying artifact {model_id}: {e}")
            return jsonify({'error': 'The artifact or GitHub project could not be found.'}), 404
            
        if not model:
            logger.warning(f"Model with ID {model_id} not found")
            return jsonify({'error': 'The artifact or GitHub project could not be found.'}), 404
            
        # Get model's license from stored metric data
        model_license = None
        if model.ndjson and isinstance(model.ndjson, dict):
            license_compliance_data = model.ndjson.get('license_compliance', {})
            if isinstance(license_compliance_data, dict):
                details = license_compliance_data.get('details', {})
                if isinstance(details, dict):
                    model_license = details.get('license')
        
        # Fallback: run license metric if no stored data
        if not model_license:
            logger.info(f"No stored license data for model {model_id}, computing on-demand")
            try:
                metric = LicenseComplianceMetric()
                context = {
                    'model_url': model.url
                }
                result = metric.compute(context)
                model_license = result.details.get('license') if result.details else None
                logger.info(f"Computed license for model {model_id}: {model_license}")
            except Exception as e:
                logger.error(f"Failed to compute license metric for model {model_id}: {e}")
                # Continue without model license - will be handled below
        
        if not model_license:
            logger.warning(f"No license information available for model {model_id}")
            return jsonify({'error': 'External license information could not be retrieved.'}), 502
            
        # Fetch GitHub license
        github_license, status = fetch_github_license(github_url)
        
        if status == 404:
            return jsonify({'error': 'The artifact or GitHub project could not be found.'}), 404
        elif status == 502:
            return jsonify({'error': 'External license information could not be retrieved.'}), 502
        model_license_normalized = normalize_license(model_license)
        github_license_normalized = normalize_license(github_license)
        
        logger.info(f"Comparing licenses - Model: '{model_license_normalized}', GitHub: '{github_license_normalized}'")
        
        compatible = (model_license_normalized == github_license_normalized) if github_license else False
        
        logger.info(f"License compatibility result for model {model_id}: {compatible}")
        return jsonify(compatible), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in license check: {str(e)}")
        return jsonify({'error': 'External license information could not be retrieved.'}), 502