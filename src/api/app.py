"""Flask application and API route definitions.

This module creates the Flask `app` instance used by the service,
registers blueprints, initializes extensions and defines the HTTP
routes that make up the Model Registry API. The top-level variable
``app`` is intentionally exported here and re-exported by the
project-level ``application.py`` so WSGI servers (and deployment
platforms like Elastic Beanstalk) can discover the callable.
"""

from flask import Flask, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, verify_jwt_in_request
from .classes import *
from src.logger import get_logger
from .auth import auth_bp, create_default_admin
from .models import User, TokenUsage, Artifact
from .config import Config, TestConfig
from .extensions import init_extensions, db
from src.url_parsers.url_type_handler import handle_url
import pickle
# from datetime import datetime, timezone
from dotenv import load_dotenv
import os

# `override=True` ensures edits to the .env file replace current os.environ values
load_dotenv(override=True)

logger = get_logger("api.app")


plannedTracks = ["Access control track"]
# model_registry = {}

app = Flask(__name__)


if os.environ.get("DEBUG", "False") == "True":
    app.config.from_object(TestConfig)
    # Record which config we loaded so prints and tests can verify it
    app.config['ACTIVE_CONFIG'] = TestConfig.__name__
else:
    app.config.from_object(Config)
    app.config['ACTIVE_CONFIG'] = Config.__name__

logger.debug(f"App running with config: {app.config.get('ACTIVE_CONFIG')}")

init_extensions(app)

with app.app_context():
    db.create_all()
    # Delete the old admin if it exists
    admin_user = User.query.filter_by(name=os.environ.get("DEFAULT_USER")).first()
    if not admin_user:
        create_default_admin()

app.register_blueprint(auth_bp)


@app.before_request
@jwt_required(optional=True)
def log_request():
    logger.info(f"Received {request.method} request for {request.path} from {request.remote_addr}")
    logger.info(f"Request body: {request.get_data(as_text=True)}")
    
@app.after_request
@jwt_required(optional=True)
def log_response(response):
    logger.info(f"Responding with status {response.status_code} and body: {response.get_data(as_text=True)}")
    return response

@app.before_request
@jwt_required(optional=True)
def enforce_request_limit():
    # Let CORS preflight (OPTIONS) pass through without auth checks
    if request.method == "OPTIONS":
        return None

    # Try to verify a JWT if one is present; do not require a token for public routes
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        # No token present or token invalid — treat as public request
        return None

    # If verify_jwt_in_request succeeded but no JWT was attached, get_jwt() will raise.
    # Guard against that by catching the RuntimeError.
    try:
        jwt_data = get_jwt()
    except RuntimeError:
        return None

    if not jwt_data:
        return None  # no token (public route)

    jti = jwt_data["jti"]
    token = TokenUsage.query.filter_by(jti=jti).first()

    if not token:
        return jsonify({"error": "Invalid or unknown token"}), 403

    if token.is_expired:
        db.session.delete(token)
        db.session.commit()
        return jsonify({"msg": "Token expired after max requests"}), 403

    try:
        token.increment_usage()
    except Exception as e:
        db.session.rollback()
        logger.exception("Error incrementing token usage: %s", e)
        return jsonify({"error": "Failed to increment token usage"}), 500

@app.route('/', methods=['GET'])
def index():
    """Index route to verify that the API is running."""
    return jsonify({'message': 'Model Registry API is running'}), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check route."""
    return jsonify({'message': 'Service reachable.'}), 200


@app.route('/artifacts', methods=['POST'])
@jwt_required()
def ArtifactsList():
    """Get any artifacts fitting the query. Search for artifacts satisfying the indicated query.

    If you want to enumerate all artifacts, provide an array with a single artifact_query whose name is "*".
    The response is paginated; the response header includes the offset to use in the next query.

    """
    res = []
    try:
        data_array = request.get_json()
        # Accept either a single artifact_query (dict) or a list containing queries
        if isinstance(data_array, dict):
            data_array = [data_array]
        if not isinstance(data_array, list) or len(data_array) == 0:
            raise ValueError("Request must contain at least one artifact query")

        data = data_array[0]
        name = data.get("name")
        types = data.get("types", [])
        if name is None:
            raise ValueError("Missing fields")
    except Exception as e:
        return jsonify({'message': 'There is missing field(s) in the artifact_query or it is formed improperly, or is invalid.'}), 400

    if len(types) == 0:
        types = ["model", "dataset", "code"]
        
    arts_by_type = Artifact.query.filter(Artifact.type.in_(types)).all()

    if name == "*":
        queried_artifacts = arts_by_type
    else:
        queried_artifacts = [art for art in arts_by_type if art.name == name]
    res = [{"id": art.id, "name": art.name, "type": art.type} for art in queried_artifacts]
    return jsonify(res), 200


@app.route('/reset', methods=['DELETE'])
@jwt_required()
def RegistryReset():
    """Reset the registry to a system default state."""
    # Only admins may reset the registry
    claims = get_jwt()
    is_admin = claims.get('is_admin', False)
    if not is_admin:
        return jsonify({'message': 'You do not have permission to reset the registry.'}), 401

    logger.info("Resetting the model registry to default state.")
    db.session.query(Artifact).delete()
    db.session.commit()
    # model_registry.clear()

    return jsonify({'message': 'Registry is reset.'}), 200


@app.route('/artifacts/<artifact_type>/<id>', methods=['GET'])
@jwt_required()
def ArtifactRetrieve(artifact_type, id):
    """Return this artifact."""
    if artifact_type not in ["model", "dataset", "code"] or not id.isdigit():
        return jsonify({'message': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400

    artifact = Artifact.query.filter_by(id=int(id)).first()
    if not artifact:
        return jsonify({'message': 'Artifact does not exist.'}), 404
    try:
        if artifact.type == artifact_type:
            metadata = {"id": artifact.id, "name": artifact.name, "type": artifact.type}
            return jsonify(metadata), 200
    except Exception as e:
        pass

    return jsonify({'message': 'Artifact does not exist.'}), 404


@app.route('/artifacts/<artifact_type>/<id>', methods=['PUT'])
@jwt_required()
def ArtifactUpdate(artifact_type, id):
    """The name, version, and id must match. The artifact source (from artifact_data) will replace the previous contents."""
    if artifact_type not in ["model", "dataset", "code"] or not id.isdigit():
        return jsonify({'message': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400
    
    try:
        req_data = request.get_json()
        metadata = req_data.get("metadata")
        upd_data = req_data.get("data")
        
        artifact = Artifact.query.filter_by(id=int(id)).first()
        if artifact and artifact.type == artifact_type and str(artifact.id) == id:
            if metadata.get("name", None):
                artifact.name = metadata.get("name")
            if metadata.get("type", None):
                artifact.type = metadata.get("type")
            if metadata.get("id", None):
                artifact.id = int(metadata.get("id"))
            if upd_data.get("download_url", None):
                artifact.download_url = upd_data.get("download_url")
            if upd_data.get("url", None):
                artifact.url = upd_data.get("url")
            db.session.commit()
            return jsonify({'message': 'Artifact is updated.'}), 200
    except Exception as e:
        logger.error(f"Error updating artifact: {e}")
        #TODO: return code on wrong request body
        #TODO: update S3 files if url is changed

    return jsonify({'message': 'Artifact does not exist.'}), 404

# NON-BASELINE
@app.route('/artifacts/<artifact_type>/<id>', methods=['DELETE'])
@jwt_required()
def ArtifactDelete(artifact_type, id):
    """Delete only the artifact that matches 'id'. (id is a unique identifier for an artifact)."""    
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>', methods=['POST'])
@jwt_required()
def ArtifactCreate(artifact_type):
    """Register a new artifact by providing a downloadable source URL. Artifacts may share a name with existing entries if their version differs.
    Refer to the description above to see how an id is formed for an artifact.
    """
    try:
        logger.info(f"Creating new artifact of type {artifact_type}")
        data = request.get_json()
        url = data.get("url")
        name = data.get("name", None)
        if artifact_type == "model":
            newArtifact = Model(url, name)
        elif artifact_type == "dataset":
            newArtifact = Dataset(url, name)
        elif artifact_type == "code":
            newArtifact = Code(url, name)
        else:
            return jsonify({'message': 'Invalid artifact_type.'}), 400
    except Exception as e:
        logger.error(f"Error creating artifact: {e}")
        return jsonify({'message': 'There is missing field(s) in the artifact_data or it is formed improperly (must include a single url)'}), 400

    #TODO: route to PostgreSQL database later
    artifact_db = Artifact(id = int(newArtifact.id), url=newArtifact.url, 
                           type=newArtifact.type, 
                           download_url=newArtifact.download_url,
                           name=newArtifact.name)
    
    try:
        db.session.add(artifact_db)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error saving artifact to database: {e}")
        return jsonify({'message': 'Failed to save artifact to database.'}), 500
    
    result = {}
    result["metadata"] = newArtifact.metadata
    result["data"] = {"url": newArtifact.url, "download_url": newArtifact.download_url}

    return jsonify(result), 201
    

@app.route('/artifact/model/<id>/rate', methods=['GET'])
@jwt_required()
def ModelArtifactRate(id):
    """Get ratings for this model artifact. (BASELINE)."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>/<id>/cost', methods=['GET'])
@jwt_required()
def get_artifact_artifact_type_id_cost(artifact_type, id):
    """Get the cost of an artifact (BASELINE)."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/byName/<name>', methods=['GET'])
@jwt_required()
def ArtifactByNameGet(name):
    """Return metadata for each version matching this artifact name."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>/<id>/audit', methods=['GET'])
@jwt_required()
def ArtifactAuditGet(artifact_type, id):
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/model/<id>/lineage', methods=['GET'])
@jwt_required()
def ArtifactLineageGet(id):
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/model/<id>/license-check', methods=['POST'])
@jwt_required()
def ArtifactLicenseCheck(id):
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/byRegEx', methods=['POST'])
@jwt_required()
def ArtifactByRegExGet():
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/tracks', methods=['GET'])
def get_tracks():
    """No description provided."""
    try:
        return jsonify({"plannedTracks": plannedTracks}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_api():
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("DEBUG", "False") == "True"
    )


if __name__ == '__main__':
    run_api() # For local testing only
