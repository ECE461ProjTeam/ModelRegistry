"""Flask application and API route definitions.

This module creates the Flask `app` instance used by the service,
registers blueprints, initializes extensions and defines the HTTP
routes that make up the Model Registry API. The top-level variable
``app`` is intentionally exported here and re-exported by the
project-level ``application.py`` so WSGI servers (and deployment
platforms like Elastic Beanstalk) can discover the callable.
"""

from datetime import datetime
from flask import Flask, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt, verify_jwt_in_request
from src.logger import get_logger
from .models import User, TokenUsage, Artifact
from .auth import auth_bp, create_default_admin, check_permissions
from .health import health_bp
from .license_check import license_check_bp
from .config import Config, TestConfig
from .extensions import init_extensions, db
from .lineage import build_lineage_graph
# from datetime import datetime, timezone
from dotenv import load_dotenv
from .s3 import clear_s3_bucket
import os
import re
from sqlalchemy import event
from sqlalchemy.orm.attributes import flag_modified
from .byRegex import regex_bp
import subprocess
import tempfile
from pathlib import Path
import uuid

# `override=True` ensures edits to the .env file replace current os.environ values
load_dotenv(override=True)

logger = get_logger("api.app")


plannedTracks = ["Access control track"]
# model_registry = {}

app = Flask(__name__)

# Disable JSON key sorting to preserve dict insertion order
app.json.sort_keys = False


if os.environ.get("DEBUG", "False") == "True":
    app.config.from_object(TestConfig)
    # Record which config we loaded so prints and tests can verify it
    app.config['ACTIVE_CONFIG'] = TestConfig.__name__
else:
    app.config.from_object(Config)
    app.config['ACTIVE_CONFIG'] = Config.__name__

logger.debug(f"App running with config: {app.config.get('ACTIVE_CONFIG')}")

app.register_blueprint(auth_bp)
app.register_blueprint(regex_bp)
app.register_blueprint(license_check_bp)
app.register_blueprint(health_bp)

init_extensions(app)

with app.app_context():
    db.create_all()
    # Delete the old admin if it exists
    admin_user = User.query.filter_by(name=os.environ.get("DEFAULT_USER")).first()
    if not admin_user:
        create_default_admin()

    # Enable REGEXP support for SQLite
    @event.listens_for(db.engine, "connect")
    def sqlite_enable_regex(conn, record):
        def regexp(pattern, string):
            reg = re.compile(pattern)
            return reg.search(string) is not None
        conn.create_function("REGEXP", 2, regexp)

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


@app.route('/artifacts', methods=['POST'])
@check_permissions('search')
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
        return jsonify({'error': 'There is missing field(s) in the artifact_query or it is formed improperly, or is invalid.'}), 400

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
@check_permissions()
def RegistryReset():
    """Reset the registry to a system default state."""
    logger.info("Resetting the model registry to default state.")
    db.session.query(Artifact).delete()
    db.session.commit()
    # model_registry.clear()
    try:
        clear_s3_bucket()
    except Exception as e:
        logger.error(f"Error clearing S3 bucket during reset: {e}")
        return jsonify({'error': 'Failed to reset the registry due to S3 error.'}), 500

    return jsonify({'message': 'Registry is reset.'}), 200

def ensure_sandbox_image():
    check = subprocess.run(
        ["docker", "images", "-q", "js-sandbox-image"],
        capture_output=True,
        text=True
    )

    if check.returncode != 0:
        raise RuntimeError(check.stderr)

    if not check.stdout.strip():
        build = subprocess.run(
            ["docker", "build", "-t", "js-sandbox-image", "-f", "Dockerfile.js-sandbox", "."],
            capture_output=True,
            text=True
        )

        if build.returncode != 0:
            raise RuntimeError(
                f"Docker build failed:\n{build.stderr}"
            )

def run_js_program(jsprog, artifact_name, uploader_name, user_name, download_url):
    if app.config['ACTIVE_CONFIG'] == TestConfig.__name__:
        ensure_sandbox_image()

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmpdir:
        workdir = Path(tmpdir)
        script_path = workdir / "script.js"
        script_path.write_text(jsprog, encoding="utf-8")
        workdir_str = str(workdir)      
        try:
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--network=none",
                    "--memory=64m",
                    "--cpus=0.5",
                    "--pids-limit=64",
                    "--read-only",
                    "--user", "root",
                    "-v", f"{workdir_str}:/sandbox:ro",
                    "js-sandbox-image",
                    "node", "/sandbox/script.js", artifact_name, uploader_name, user_name, download_url
                ],
                capture_output=True,
                text=True,
                timeout=3
            )
                        
            return True, result.returncode, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, -1, "JS program timed out"

@app.route('/artifacts/<artifact_type>/<id>', methods=['GET'])
@check_permissions("search", "download")
def ArtifactRetrieve(artifact_type, id):
    """Return this artifact."""
    if artifact_type not in ["model", "dataset", "code"]:
        return jsonify({'error': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400

    if not id.isdigit():
        return jsonify({'error': 'Artifact does not exist.'}), 404

    artifact = Artifact.query.filter_by(id=int(id)).first()
    if not artifact:
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    res = {}
    
    if artifact.type == artifact_type:
        metadata = {"id": artifact.id, "name": artifact.name, "type": artifact.type}
        data = {"url": artifact.url, "download_url": artifact.download_url}
        res.update({"metadata": metadata, "data": data})

        if artifact.sensitive:
            # Run JS program here
            jsprog = artifact.js_program
            user = get_jwt_identity()
                        
            passed, code, message = run_js_program(jsprog, artifact.name, artifact.uploader_name, user, artifact.download_url)
            
            if not passed:
                res["message"] = message
                res["data"]["download_url"] = ""
                return_code = 203
            
            elif code != 0:
                res["stdout"] = message
                res["message"] = "JS program returned non-zero exit code"
                res["data"]["download_url"] = ""
                return_code = 202

            else:
                logger.info(f"Sensitive model download authorized")
                # Log download history
                history = artifact.download_history
                history.append({"timestamp": str(datetime.now()), "username": user})
                artifact.download_history = history
                flag_modified(artifact, "download_history")
                db.session.commit()
                res['stdout'] = message
                res["message"] = "JS program executed successfully. Download Authorized."
                return_code = 200
        else:
            return_code = 200
                        
        return jsonify(res), return_code

    return jsonify({'error': 'Artifact does not exist.'}), 404

@app.route('/artifact/model/<id>/download_history', methods=['GET'])
@check_permissions("search", "download")
def ArtifactDownloadHistory(id):
    
    if not id.isdigit():
        return jsonify({'error': 'There is missing field(s) in the artifact_id or it is formed improperly, or is invalid.'}), 400
    model = Artifact.query.filter_by(id=int(id), type='model', sensitive=True).first()
    if not model:
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    return jsonify({'download_history': model.download_history}), 200
    


@app.route('/artifacts/<artifact_type>/<id>', methods=['PUT'])
@check_permissions("upload", "search")
def ArtifactUpdate(artifact_type, id):
    """The name, version, and id must match. The artifact source (from artifact_data) will replace the previous contents."""
    if artifact_type not in ["model", "dataset", "code"]:
        return jsonify({'error': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400
    
    if not id.isdigit():
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
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

    return jsonify({'error': 'Artifact does not exist.'}), 404

# NON-BASELINE
@app.route('/artifacts/<artifact_type>/<id>', methods=['DELETE'])
@check_permissions()
def ArtifactDelete(artifact_type, id):
    if artifact_type not in ["model", "dataset", "code"]:
        return jsonify({'error': 'There is missing field(s) in the artifact_type or artifact_id or invalid.'}), 400
    
    if not id.isdigit():
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    artifact = Artifact.query.filter_by(id=int(id), type=artifact_type).first()
    if not artifact:
        return jsonify({'error': 'Artifact does not exist.'}), 404

    db.session.delete(artifact)
    db.session.commit()

    if Artifact.query.filter_by(id=int(id), type=artifact_type).first():
        return jsonify({'message': 'Deletion failed.'}), 500
    
    return jsonify({'message': 'Artifact is deleted.'}), 200


@app.route('/artifact/<artifact_type>', methods=['POST'])
@check_permissions("upload", "search")
def ArtifactCreate(artifact_type):
    """Register a new artifact by providing a downloadable source URL. Artifacts may share a name with existing entries if their version differs.
    Refer to the description above to see how an id is formed for an artifact.
    """
    try:
        logger.info(f"Creating new artifact of type {artifact_type}")
        data = request.get_json()
        url = data.get("url", None)
        if url is None:
            raise ValueError("Missing fields")
        name = data.get("name", None)
        if artifact_type not in ["model", "dataset", "code"]:
            return jsonify({'error': 'Invalid artifact_type.'}), 400
        sensitive = data.get("sensitive", False)
        user = get_jwt_identity()
        js_program = None
        if sensitive:
            js_program = data.get("js_program", None)
            if js_program is None or js_program.strip() == "":
                return jsonify({'error': 'Sensitive artifact must include a js_program field.'}), 400
            
    except Exception as e:
        logger.error(f"Error creating artifact: {e}")
        return jsonify({'error': 'There is missing field(s) in the artifact_data or it is formed improperly (must include a single url)'}), 400
    
    if artifact_type == "model" and Artifact.is_valid_hf_url(url) is False:
            return jsonify({'error': 'The provided URL is not a valid Hugging Face model URL.'}), 400
        
    if artifact_type == "code" and Artifact.is_valid_git_url(url) is False:
            return jsonify({'error': 'The provided URL is not a valid Git repository URL.'}), 400
        
    if artifact_type == "dataset" and Artifact.is_valid_url(url) is False:
            return jsonify({'error': 'The provided URL is not a valid HTTP/HTTPS URL.'}), 400

    artifact_db = Artifact(id = Artifact.make_id(), url=url, 
                           type=artifact_type, 
                           download_url="",
                           name=name, 
                           sensitive=sensitive,
                           js_program=js_program if sensitive else None,
                           uploader_name=user)
    
    if artifact_db.ingestible:
        try:
            db.session.add(artifact_db)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error saving artifact to database: {e}")
            return jsonify({'error': 'Failed to save artifact to database.'}), 500
    else:
        return jsonify({'error': 'Artifact is not registered due to the disqualified rating.'}), 424
    
    result = {}
    result["metadata"] = {"id": artifact_db.id, "name": artifact_db.name, "type": artifact_db.type}
    result["data"] = {"url": artifact_db.url, "download_url": artifact_db.download_url}

    return jsonify(result), 201
    

@app.route('/artifact/model/<id>/rate', methods=['GET'])
@check_permissions("search")
def ModelArtifactRate(id):
    """Get ratings for this model artifact. (BASELINE).
    
    This endpoint handles two scenarios:
    1. Initial rating (ndjson empty): Computes all metrics, sets tree_score = net_score
    2. Re-rating (ndjson populated): Recomputes tree_score from lineage graph, recalculates net_score
    """
    
    if id is None:
        return jsonify({'error': 'There is missing field(s) in the artifact_id or it is formed improperly, or is invalid.'}), 400
    
    if not id.isdigit():
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    art = Artifact.query.filter_by(id=int(id)).first()
    if art is None or art.type != "model":
        return jsonify({'error': 'Artifact does not exist.'}), 404

    # Determine if this is initial rating or re-rating
    is_initial = (art.ndjson == {} or art.ndjson is None)
    logger.info(f"Rating artifact {id} - {'Initial rating' if is_initial else 'Re-rating (computing from lineage)'}")

    try:
        if not art.rate():
            logger.error(f"Rating failed for artifact {id}")
            return jsonify({'error': 'The artifact rating system encountered an error while computing at least one metric.'}), 500
        
        # Commit the updated ndjson to database
        db.session.commit()
        logger.info(f"Successfully rated artifact {id} and committed to database")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during rating of artifact {id}: {e}")
        return jsonify({'error': 'The artifact rating system encountered an error while computing at least one metric.'}), 500

    if not art.check_ingestible():
        logger.warning(f"Artifact {id} is not ingestible after rating (scores below threshold)")
        # Note: Not returning 424 as per original code comment

    return jsonify(art.ndjson), 200


@app.route('/artifact/<artifact_type>/<id>/cost', methods=['GET'])
@check_permissions("search")
def get_artifact_artifact_type_id_cost(artifact_type, id):
    """Get the cost of an artifact (BASELINE)."""
    
    if artifact_type not in ["model", "dataset", "code"]:
        return jsonify({'error': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400
    
    if not id.isdigit():
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    art = Artifact.query.filter_by(id=int(id)).first()
    if art is None or art.type != artifact_type:
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    result = {}
    result[id] = {"total_cost": art.cost}
    return jsonify(result), 200


@app.route('/artifact/byName/<name>', methods=['GET'])
@check_permissions("search")
def ArtifactByNameGet(name):
    """Return metadata for each version matching this artifact name."""
    if not name:
        return jsonify({'message': 'There is missing field(s) in the artifact_name or it is formed improperly, or is invalid.'}), 400

    if name == "*":
        artifacts = Artifact.query.all()
    else:
        artifacts = Artifact.query.filter_by(name=name).all()

    if not artifacts:
        return jsonify({'message': 'No such artifact.'}), 404    
    
    res = [{"name": art.name, "id": art.id, "type": art.type} for art in artifacts]
    return jsonify(res), 200


@app.route('/artifact/<artifact_type>/<id>/audit', methods=['GET'])
@check_permissions("search")
def ArtifactAuditGet(artifact_type, id):
    """No message provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/model/<id>/lineage', methods=['GET'])
@check_permissions("search")
def ArtifactLineageGet(id):
    """Retrieve the lineage graph for a model artifact.
    
    Returns a graph with nodes (models) and edges (parent-child relationships)
    based on stored lineage metadata. Only includes ingested models.
    """
    if id is None:
        return jsonify({'error': 'There is missing field(s) in the artifact_id or it is formed improperly, or is invalid.'}), 400
    
    if not id.isdigit():
        return jsonify({'error': 'Artifact does not exist.'}), 404
    
    try:
        # Get the target artifact
        target_artifact = Artifact.query.filter_by(id=int(id), type='model').first()
        
        if not target_artifact:
            return jsonify({'error': 'Artifact does not exist.'}), 404
        
        # Check if lineage data exists
        if not target_artifact.ndjson or 'lineage' not in target_artifact.ndjson:
            logger.warning(f"Artifact {id} has no lineage metadata")
            return jsonify({
                'error': 'The lineage graph cannot be computed because the artifact metadata is missing or malformed.'}), 400
        
        # Get all other model artifacts from database
        all_artifacts = Artifact.query.filter(
            Artifact.type == 'model',
            Artifact.id != int(id)
        ).all()
        
        # Build the lineage graph
        lineage_graph = build_lineage_graph(target_artifact, all_artifacts)
        
        return jsonify(lineage_graph), 200
        
    except Exception as e:
        logger.error(f"Error building lineage graph for artifact {id}: {e}")
        return jsonify({
            'error': 'The lineage graph cannot be computed because the artifact metadata is missing or malformed.'
        }), 400


@app.route('/tracks', methods=['GET'])
def get_tracks():
    """No message provided."""
    try:
        return jsonify({"plannedTracks": plannedTracks}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_api():
    app.run(
        host='localhost',
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("DEBUG", "False") == "True"
    )


if __name__ == '__main__':
    run_api() # For local testing only
