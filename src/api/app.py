from flask import Flask, jsonify, request

plannedTracks = ["Access control track"]

app = Flask(__name__)


@app.route('/artifacts', methods=['POST'])
def ArtifactsList():
    """Get any artifacts fitting the query. Search for artifacts satisfying the indicated query.

    If you want to enumerate all artifacts, provide an array with a single artifact_query whose name is "*".
    The response is paginated; the response header includes the offset to use in the next query.

    In the Request Body below, "version" has all the possible inputs. The "version" cannot be a combination of the different possibilities.
    """
    return jsonify({'message': 'Not implemented-artifacts'}), 501


@app.route('/reset', methods=['DELETE'])
def RegistryReset():
    """Reset the registry to a system default state."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifacts/<artifact_type>/<id>', methods=['GET'])
def ArtifactRetrieve(artifact_type, id):
    """Return this artifact."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifacts/<artifact_type>/<id>', methods=['PUT'])
def ArtifactUpdate(artifact_type, id):
    """The name, version, and id must match. The artifact source (from artifact_data) will replace the previous contents."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifacts/<artifact_type>/<id>', methods=['DELETE'])
def ArtifactDelete(artifact_type, id):
    """Delete only the artifact that matches 'id'. (id is a unique identifier for an artifact)."""
    return jsonify({'message': 'Not implemented'}), 501


@app.route('/artifact/<artifact_type>', methods=['POST'])
def ArtifactCreate(artifact_type):
    """Register a new artifact by providing a downloadable source URL. Artifacts may share a name with existing entries if their version differs.
    Refer to the description above to see how an id is formed for an artifact.
    """
    return jsonify({'message': 'Not implemented'}), 501


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


if __name__ == '__main__':
    # Can test with curl -X <METHOD> http://127.0.0.1:5000/<command>
    app.run(host='0.0.0.0', port=5000, debug=True)
