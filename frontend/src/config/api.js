// frontend/src/config/api.js

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001';

// Endpoints mirror the Flask routes defined in src/api/app.py
const API_ENDPOINTS = {
    HEALTH: `${API_BASE_URL}/health`,
    AUTHENTICATE: `${API_BASE_URL}/authenticate`,
    REGISTER: `${API_BASE_URL}/register`,
    PROFILE: `${API_BASE_URL}/profile`,
    USERS: `${API_BASE_URL}/users`,

    // Artifacts collection (search/list)
    ARTIFACTS: `${API_BASE_URL}/artifacts`,

    // Artifact by type + id (GET/PUT/DELETE)
    ARTIFACT_BY_TYPE_ID: (type, id) => `${API_BASE_URL}/artifacts/${type}/${id}`,

    // Create artifact: POST /artifact/<artifact_type>
    ARTIFACT_CREATE: (type) => `${API_BASE_URL}/artifact/${type}`,

    // Additional artifact-related endpoints
    ARTIFACT_RATE: (id) => `${API_BASE_URL}/artifact/model/${id}/rate`,
    ARTIFACT_COST: (type, id) => `${API_BASE_URL}/artifact/${type}/${id}/cost`,
    ARTIFACT_BY_NAME: (name) => `${API_BASE_URL}/artifact/byName/${name}`,
    ARTIFACT_AUDIT: (type, id) => `${API_BASE_URL}/artifact/${type}/${id}/audit`,
    ARTIFACT_LINEAGE: (id) => `${API_BASE_URL}/artifact/model/${id}/lineage`,
    ARTIFACT_LICENSE_CHECK: (id) => `${API_BASE_URL}/artifact/model/${id}/license-check`,
    ARTIFACT_BY_REGEX: `${API_BASE_URL}/artifact/byRegEx`,

    RESET: `${API_BASE_URL}/reset`,
    TRACKS: `${API_BASE_URL}/tracks`,
};

export default API_ENDPOINTS;
export { API_BASE_URL, API_ENDPOINTS };
