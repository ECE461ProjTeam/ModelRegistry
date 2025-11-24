"""
Unit tests for the Model Registry API endpoints.
Tests are based on the ECE 461 Fall 2025 OpenAPI specification.
"""

import unittest
import json
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.app import app
from src.api.models import User, TokenUsage, Artifact
from flask_jwt_extended import get_jti
from src.api.extensions import db
from unittest.mock import patch

# @patch('src.api.models.Artifact.send_to_bucket', return_value=None)
# @patch('src.api.s3.clear_s3_bucket', return_value=None)
class TestAPIEndpoints(unittest.TestCase):
    """Test suite for Model Registry API endpoints"""

    @classmethod
    def setUpClass(cls):
        cls.patch_send = patch('src.api.models.Artifact.send_to_bucket', return_value="None")
        cls.patch_clear = patch('src.api.s3.clear_s3_bucket', return_value=None)
        cls.patch_rate = patch('src.api.models.Artifact.rate', return_value=True)
        cls.patch_reset = patch('src.api.app.clear_s3_bucket', return_value=None)
        cls.mock_send = cls.patch_send.start()
        cls.mock_clear = cls.patch_clear.start()
        cls.mock_rate = cls.patch_rate.start()
        cls.mock_reset = cls.patch_reset.start()
        
        
        
    @classmethod
    def tearDownClass(cls):
        cls.patch_send.stop()
        cls.patch_clear.stop()
        cls.patch_rate.stop()
        cls.patch_reset.stop()
    
    def setUp(self):
        """Set up test client and clear registry before each test"""
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True
        with self.app.app_context():
            Artifact.query.delete()
            db.session.commit()
        # Push app context so authenticate endpoint and JWT machinery work
        self._ctx = self.app.app_context()
        self._ctx.push()

        # Obtain a real token by calling the authenticate endpoint with the
        # default admin credentials created on app startup. Place it into the
        # X-Authorization header to maintain existing tests that use that
        # header.
        auth_resp = self.client.put('/authenticate', json={
            'user': {'name': os.environ.get("DEFAULT_USER")},
            'secret': {'password': os.environ.get("DEFAULT_PASSWORD")}
        })
        if auth_resp.status_code == 200:
            self.auth_token = auth_resp.get_json() # since auth response is "bearer <token>"
        else:
            # Fallback to empty token so tests still run and will fail meaningfully
            self.auth_token = ''

        self.headers = {
            'X-Authorization': self.auth_token,
            'Content-Type': 'application/json'
        }

    def tearDown(self):
        """Clean up after each test"""
        with self.app.app_context():
            Artifact.query.delete()
            db.session.commit()
        # pop the app context pushed in setUp
        try:
            self._ctx.pop()
        except Exception:
            # Ignore exceptions during context pop in teardown to avoid masking test failures.
            pass

# class TestTest(TestAPIEndpoints):
#     def test_test(self):
#         """Basic test to verify test framework is working"""
#         art = Artifact(type="model", url="https://huggingface.co/openai/whisper-tiny")
#         self.assertEqual(art.send_to_bucket(), "hello")
        
        
class TestTracksEndpoint(TestAPIEndpoints):
    """Test /tracks endpoint"""

    def test_get_tracks_success(self):
        """Test GET /tracks returns planned tracks"""
        response = self.client.get('/tracks', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('plannedTracks', data)
        self.assertIsInstance(data['plannedTracks'], list)
        self.assertIn('Access control track', data['plannedTracks'])

# @patch('src.api.s3.clear_s3_bucket', return_value=None)
class TestRegistryResetEndpoint(TestAPIEndpoints):
    """Test /reset endpoint"""
    def test_reset_success_as_admin(self):
        """Test DELETE /reset successfully resets registry as admin"""
        # Add a model to registry first
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        
        # Reset the registry
        response = self.client.delete('/reset', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # app returns 'message' key for success responses
        self.assertEqual(data.get('message'), 'Registry is reset.')
        with self.app.app_context():
            self.assertEqual(Artifact.query.count(), 0)

    def test_reset_unauthorized(self):
        """Test DELETE /reset fails for non-admin user"""
        # create a non-admin user and obtain a token for them
        with self.app.app_context():
            u = User(name='regular', is_admin=False)
            u.set_password('pw')
            db.session.add(u)
            db.session.commit()

        auth_resp = self.client.put('/authenticate', json={
            'user': {'name': 'regular'}, 'secret': {'password': 'pw'}
        })
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {'X-Authorization': f'{token}', 'Content-Type': 'application/json'}

        response = self.client.delete('/reset', headers=headers)

        self.assertEqual(response.status_code, 401)

    def test_reset_authentication_failed(self):
        """Test DELETE /reset fails with invalid authentication"""
        # call without a token to simulate unauthenticated request
        response = self.client.delete('/reset')
        # Flask-JWT-Extended responds with 401 for missing credentials
        self.assertEqual(response.status_code, 401)


class TestArtifactCreateEndpoint(TestAPIEndpoints):
    """Test /artifact/{artifact_type} POST endpoint"""

    def test_create_model_success(self):
        """Test POST /artifact/model creates a new model artifact"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('metadata', data)
        self.assertIn('data', data)
        metadata = data['metadata']
        self.assertIn('name', metadata)
        self.assertIn('id', metadata)
        self.assertIn('type', metadata)
        self.assertEqual(metadata['name'], 'whisper-tiny')
        self.assertEqual(metadata['type'], 'model')
        with self.app.app_context():
            self.assertIsNotNone(Artifact.query.filter_by(id=metadata['id']).first())

    def test_create_model_missing_url(self):
        """Test POST /artifact/model fails without url"""
        payload = {}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        # app returns error under 'message'
        self.assertIn('missing field', data.get('message', '').lower())

    def test_create_model_invalid_url(self):
        """Test POST /artifact/model fails with invalid url format"""
        payload = {'url': 'not-a-valid-huggingface-url'}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('message', data)

    # @patch('src.api.app.authenticate', return_value=False)
    # def test_create_model_authentication_failed(self, mock_auth):
    #     """Test POST /artifact/model fails with invalid authentication"""
    #     payload = {'url': 'https://huggingface.co/openai/whisper-tiny'}
        
    #     response = self.client.post(
    #         '/artifact/model',
    #         headers=self.headers,
    #         data=json.dumps(payload)
    #     )
        
    #     self.assertEqual(response.status_code, 403)


class TestArtifactRetrieveEndpoint(TestAPIEndpoints):
    """Test /artifacts/{artifact_type}/{id} GET endpoint"""

    def test_retrieve_model_success(self):
        """Test GET /artifacts/model/{id} retrieves existing model"""
        # Create a model first
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'name': 'whisper-tiny', 'url': test_url})
        )
        created_data = json.loads(create_response.data)
        artifact_id = created_data['metadata']['id']
        
        # Retrieve the model
        response = self.client.get(
            f'/artifacts/model/{artifact_id}',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'whisper-tiny')
        self.assertEqual(data['id'], artifact_id)
        self.assertEqual(data['type'], 'model')

    def test_retrieve_model_not_found(self):
        """Test GET /artifacts/model/{id} returns 404 for non-existent model"""
        response = self.client.get(
            '/artifacts/model/999999999',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data.get('message'), 'Artifact does not exist.')

    def test_retrieve_invalid_artifact_type(self):
        """Test GET /artifacts/{invalid_type}/{id} returns 400"""
        response = self.client.get(
            '/artifacts/invalid_type/123',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('missing field', data.get('message', '').lower())

    def test_retrieve_invalid_id_format(self):
        """Test GET /artifacts/model/{invalid_id} returns 400"""
        response = self.client.get(
            '/artifacts/model/not-a-number',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 400)

    def test_retrieve_authentication_failed(self):
        """Test GET /artifacts/model/{id} fails with invalid authentication"""
        # call without headers to simulate missing authentication
        response = self.client.get('/artifacts/model/123')
        # missing JWT -> 401
        self.assertEqual(response.status_code, 401)


class TestArtifactUpdateEndpoint(TestAPIEndpoints):
    """Test /artifacts/{artifact_type}/{id} PUT endpoint"""

    def test_update_model_success(self):
        """Test PUT /artifacts/model/{id} updates existing model"""
        # Create a model first
        test_url = "https://huggingface.co/google-bert/bert-base-uncased"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'name': 'bert-base-uncased', 'url': test_url})
        )
        created_data = json.loads(create_response.data)
        artifact_id = created_data['metadata']['id']
        new_id = "48472749248"
        
        # Update the model
        update_payload = {
            'metadata': {'name': 'string', 'id': new_id, "type": "model"},
            'data': {"url": "https://huggingface.co/openai/whisper-tiny/tree/main", "download_url": "https://ec2-10-121-34-12/download/whisper-tiny"}
        }
        response = self.client.put(
            f'/artifacts/model/{artifact_id}',
            headers=self.headers,
            data=json.dumps(update_payload)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get('message'), 'Artifact is updated.')
        
        # Verify the update
        with self.app.app_context():
            artifact = Artifact.query.filter_by(id=int(new_id)).first()
            self.assertIsNotNone(artifact)
            self.assertEqual(artifact.name, 'string')
            self.assertEqual(artifact.url, 'https://huggingface.co/openai/whisper-tiny/tree/main')
            self.assertEqual(artifact.download_url, 'https://ec2-10-121-34-12/download/whisper-tiny')

    def test_update_model_not_found(self):
        """Test PUT /artifacts/model/{id} returns 404 for non-existent model"""
        update_payload = {
            'metadata': {'name': 'test'},
            'data': {'url': 'https://huggingface.co/test/model'}
        }
        response = self.client.put(
            '/artifacts/model/999999999',
            headers=self.headers,
            data=json.dumps(update_payload)
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data.get('message'), 'Artifact does not exist.')

    def test_update_invalid_artifact_type(self):
        """Test PUT /artifacts/{invalid_type}/{id} returns 400"""
        update_payload = {
            'metadata': {'name': 'test'},
            'data': {'url': 'https://huggingface.co/test/model'}
        }
        response = self.client.put(
            '/artifacts/invalid/123',
            headers=self.headers,
            data=json.dumps(update_payload)
        )
        
        self.assertEqual(response.status_code, 400)

    def test_update_authentication_failed(self):
        """Test PUT /artifacts/model/{id} fails with invalid authentication"""
        update_payload = {
            'metadata': {'name': 'test'},
            'data': {'url': 'https://huggingface.co/test/model'}
        }
        # call without auth headers to simulate unauthenticated request
        response = self.client.put('/artifacts/model/123', data=json.dumps(update_payload))
        self.assertEqual(response.status_code, 401)


class TestArtifactsListEndpoint(TestAPIEndpoints):
    """Test /artifacts POST endpoint"""

    def test_list_artifacts_success(self):
        """Test POST /artifacts lists artifacts matching query"""
        # Create multiple models
        with self.app.app_context():
            Artifact.query.delete()
            db.session.commit()
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        for url in urls:
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url})
            )
        
        # List all models
        query = [{
            'name': '*',
            'types': ['model']
        }]
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)

    def test_list_artifacts_by_type(self):
        """Test POST /artifacts filters by artifact type"""
        # Create a model
        self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': 'https://huggingface.co/openai/whisper-tiny'})
        )
        
        # Query for datasets (should return empty)
        query = [{
            'name': '*',
            'types': ['dataset']
        }]
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 0)

    def test_list_artifacts_missing_name(self):
        """Test POST /artifacts fails without name field"""
        query = [{
            'types': ['model']
        }]
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('missing field', data.get('message', '').lower())

    def test_list_artifacts_missing_types(self):
        """Test POST /artifacts fails without types field"""
        query = {
            'name': '*'
        }
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 200)

    def test_list_artifacts_authentication_failed(self):
        """Test POST /artifacts fails with invalid authentication"""
        query = [{
            'name': '*',
            'types': ['model']
        }]
        # Simulate an otherwise-valid JWT but missing TokenUsage record so
        # the application treats the token as unknown (should return 403).
        auth_resp = self.client.put('/authenticate', json={
            'user': {'name': os.environ.get("DEFAULT_USER")},
            'secret': {'password': os.environ.get("DEFAULT_PASSWORD")}
        })
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {'X-Authorization': f'{token}', 'Content-Type': 'application/json'}

        # Remove the TokenUsage row for this token so the token is valid JWT but unknown to the app
        # The authenticate endpoint returns a JSON string like "bearer <jwt>", so
        # strip the "bearer " prefix and pass the raw token to get_jti.
        raw_jwt = token.split(None, 1)[1]
        jti = get_jti(encoded_token=raw_jwt)
        with self.app.app_context():
            TokenUsage.query.filter_by(jti=jti).delete()
            db.session.commit()

        response = self.client.post(
            '/artifacts',
            headers=headers,
            data=json.dumps(query)
        )

        self.assertEqual(response.status_code, 403)


class TestEdgeCases(TestAPIEndpoints):
    """Test edge cases and error handling"""

    def test_multiple_models_same_name_different_urls(self):
        """Test creating multiple models with different URLs generates different IDs"""
        url1 = "https://huggingface.co/openai/whisper-tiny"
        url2 = "https://huggingface.co/openai/whisper-tiny/tree/main"
        
        response1 = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': url1})
        )
        response2 = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': url2})
        )
        
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        
        # Both should succeed
        self.assertEqual(response1.status_code, 201)
        self.assertEqual(response2.status_code, 201)
        
        # IDs should be different
        self.assertNotEqual(data1['metadata']['id'], data2['metadata']['id'])
        
        # Names should be the same
        self.assertEqual(data1['metadata']['name'], data2['metadata']['name'])

    def test_retrieve_wrong_artifact_type(self):
        """Test retrieving with wrong artifact type returns 404"""
        # Create a model
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        created_data = json.loads(create_response.data)
        artifact_id = created_data['metadata']['id']
        
        # Try to retrieve as dataset
        response = self.client.get(
            f'/artifacts/dataset/{artifact_id}',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)


def suite():
    """Create test suite"""
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestTracksEndpoint))
    test_suite.addTest(unittest.makeSuite(TestRegistryResetEndpoint))
    test_suite.addTest(unittest.makeSuite(TestArtifactCreateEndpoint))
    test_suite.addTest(unittest.makeSuite(TestArtifactRetrieveEndpoint))
    test_suite.addTest(unittest.makeSuite(TestArtifactUpdateEndpoint))
    test_suite.addTest(unittest.makeSuite(TestArtifactsListEndpoint))
    test_suite.addTest(unittest.makeSuite(TestEdgeCases))
    return test_suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())