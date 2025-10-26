from flask import Flask, jsonify, request
from .classes import *
from src.logger import get_logger
from .auth import authenticate, getPermissionLevel
logger = get_logger("api.app")

plannedTracks = ["Access control track"]
model_registry = {}

app = Flask(__name__)


@app.route('/artifacts', methods=['POST'])
def ArtifactsList():
    """Get any artifacts fitting the query. Search for artifacts satisfying the indicated query.

    If you want to enumerate all artifacts, provide an array with a single artifact_query whose name is "*".
    The response is paginated; the response header includes the offset to use in the next query.

    """
    
    if not authenticate():
        return jsonify({'description': 'Authentication failed due to invalid or missing AuthenticationToken.'}), 403
    
    res = {}
    try:
        data = request.get_json()
        name = data.get("name")
        types = data.get("types")
        if name is None or types is None:
            raise ValueError("Missing fields")
    except Exception as e:
        return jsonify({'description': 'There is missing field(s) in the artifact_query or it is formed improperly, or is invalid.'}), 400
    
    for model in model_registry.values():
        if model.type in types:
            res[model.name] = model.metadata
    #TODO: pagination?
    #TODO: too many artifacts?
    return jsonify(res), 200


@app.route('/reset', methods=['DELETE'])
def RegistryReset():
    """Reset the registry to a system default state."""
    
    if not authenticate():
        return jsonify({'description': 'Authentication failed due to invalid or missing AuthenticationToken.'}), 403
    
    if getPermissionLevel() != "admin":
        return jsonify({'description': 'You do not have permission to reset the registry.'}), 401
    
    logger.info("Resetting the model registry to default state.")
    model_registry.clear()
    return jsonify({'description': 'Registry is reset.'}), 200


@app.route('/artifacts/<artifact_type>/<id>', methods=['GET'])
def ArtifactRetrieve(artifact_type, id):
    """Return this artifact."""
    
    if not authenticate():
        return jsonify({'description': 'Authentication failed due to invalid or missing AuthenticationToken.'}), 403
    
    if artifact_type not in ["model", "dataset", "code"] or not id.isdigit():
        return jsonify({'description': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400

    print(model_registry)

    if id not in model_registry:
        return jsonify({'description': 'Artifact does not exist.'}), 404
    try:
        model = model_registry[id]
        print(model.id)
        if model.type == artifact_type and str(model.id) == id:
            return jsonify(model.metadata), 200
    except Exception as e:
        pass

    return jsonify({'description': 'Artifact does not exist.'}), 404


@app.route('/artifacts/<artifact_type>/<id>', methods=['PUT'])
def ArtifactUpdate(artifact_type, id):
    """The name, version, and id must match. The artifact source (from artifact_data) will replace the previous contents."""
    
    if not authenticate():
        return jsonify({'description': 'Authentication failed due to invalid or missing AuthenticationToken.'}), 403
    
    if artifact_type not in ["model", "dataset", "code"] or not id.isdigit():
        return jsonify({'description': 'There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.'}), 400
    
    try:
        req_data = request.get_json()
        metadata = req_data.get("metadata")
        upd_data = req_data.get("data")
        
        model = model_registry[id]
        if model.type == artifact_type and model.id == id:
            model_registry[id].metadata.update(metadata)
            model_registry[id].url = upd_data.get("url")
            return jsonify({'description': 'Artifact is updated.'}), 200
    except Exception as e:
        pass
        #TODO: return code on wrong request body

    return jsonify({'description': 'Artifact does not exist.'}), 404


@app.route('/artifacts/<artifact_type>/<id>', methods=['DELETE'])
def ArtifactDelete(artifact_type, id):
    """Delete only the artifact that matches 'id'. (id is a unique identifier for an artifact)."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>', methods=['POST'])
def ArtifactCreate(artifact_type):
    """Register a new artifact by providing a downloadable source URL. Artifacts may share a name with existing entries if their version differs.
    Refer to the description above to see how an id is formed for an artifact.
    """
    try:
        logger.info(f"Creating new artifact of type {artifact_type}")
        data = request.get_json()
        url = data.get("url")
        newModel = Model(url)
        logger.info(f"Created new model artifact with name: {newModel.name}")
        model_registry[newModel.id] = newModel  # change to work with S3
        return jsonify(newModel.metadata), 201
    except Exception as e:
        return jsonify({'description': 
            'There is missing field(s) in the artifact_data or it is formed improperly (must include a single url)'}), 400
        


@app.route('/artifact/model/<id>/rate', methods=['GET'])
def ModelArtifactRate(id):
    """Get ratings for this model artifact. (BASELINE)."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>/<id>/cost', methods=['GET'])
def get_artifact_artifact_type_id_cost(artifact_type, id):
    """Get the cost of an artifact (BASELINE)."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/authenticate', methods=['PUT'])
def CreateAuthToken():
    """Create an access token."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/byName/<name>', methods=['GET'])
def ArtifactByNameGet(name):
    """Return metadata for each version matching this artifact name."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>/<id>/audit', methods=['GET'])
def ArtifactAuditGet(artifact_type, id):
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/model/<id>/lineage', methods=['GET'])
def ArtifactLineageGet(id):
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/model/<id>/license-check', methods=['POST'])
def ArtifactLicenseCheck(id):
    """No description provided."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/byRegEx', methods=['POST'])
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
    app.run(host='0.0.0.0', port=5000, debug=True)
