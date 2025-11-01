"""
Unit tests for the Model Registry API endpoints.
Tests are based on the ECE 461 Fall 2025 OpenAPI specification.
"""

import unittest
import json
import sys
from unittest.mock import patch, MagicMock
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.app import app, model_registry


class TestAPIEndpoints(unittest.TestCase):
    """Test suite for Model Registry API endpoints"""

    def setUp(self):
        """Set up test client and clear registry before each test"""
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True
        model_registry.clear()
        
        # Mock authentication token
        self.auth_token = "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        self.headers = {
            'X-Authorization': self.auth_token,
            'Content-Type': 'application/json'
        }

    def tearDown(self):
        """Clean up after each test"""
        model_registry.clear()


class TestTracksEndpoint(TestAPIEndpoints):
    """Test /tracks endpoint"""

    def test_get_tracks_success(self):
        """Test GET /tracks returns planned tracks"""
        response = self.client.get('/tracks')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('plannedTracks', data)
        self.assertIsInstance(data['plannedTracks'], list)
        self.assertIn('Access control track', data['plannedTracks'])


class TestRegistryResetEndpoint(TestAPIEndpoints):
    """Test /reset endpoint"""

    @patch('src.api.app.authenticate', return_value=True)
    @patch('src.api.app.getPermissionLevel', return_value='admin')
    def test_reset_success_as_admin(self, mock_perm, mock_auth):
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
        self.assertEqual(data['description'], 'Registry is reset.')
        self.assertEqual(len(model_registry), 0)

    @patch('src.api.app.authenticate', return_value=True)
    @patch('src.api.app.getPermissionLevel', return_value='user')
    def test_reset_unauthorized(self, mock_perm, mock_auth):
        """Test DELETE /reset fails for non-admin user"""
        response = self.client.delete('/reset', headers=self.headers)
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'You do not have permission to reset the registry.')

    @patch('src.api.app.authenticate', return_value=False)
    def test_reset_authentication_failed(self, mock_auth):
        """Test DELETE /reset fails with invalid authentication"""
        response = self.client.delete('/reset', headers=self.headers)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'Authentication failed due to invalid or missing AuthenticationToken.')


class TestArtifactCreateEndpoint(TestAPIEndpoints):
    """Test /artifact/{artifact_type} POST endpoint"""

    @patch('src.api.app.authenticate', return_value=True)
    def test_create_model_success(self, mock_auth):
        """Test POST /artifact/model creates a new model artifact"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'url': test_url}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('name', data)
        self.assertIn('id', data)
        self.assertIn('type', data)
        self.assertEqual(data['name'], 'whisper-tiny')
        self.assertEqual(data['type'], 'model')
        self.assertIn(data['id'], model_registry)

    @patch('src.api.app.authenticate', return_value=True)
    def test_create_model_missing_url(self, mock_auth):
        """Test POST /artifact/model fails without url"""
        payload = {}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('description', data)
        self.assertIn('missing field', data['description'].lower())

    @patch('src.api.app.authenticate', return_value=True)
    def test_create_model_invalid_url(self, mock_auth):
        """Test POST /artifact/model fails with invalid url format"""
        payload = {'url': 'not-a-valid-huggingface-url'}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('description', data)

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

    @patch('src.api.app.authenticate', return_value=True)
    def test_retrieve_model_success(self, mock_auth):
        """Test GET /artifacts/model/{id} retrieves existing model"""
        # Create a model first
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']
        
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

    @patch('src.api.app.authenticate', return_value=True)
    def test_retrieve_model_not_found(self, mock_auth):
        """Test GET /artifacts/model/{id} returns 404 for non-existent model"""
        response = self.client.get(
            '/artifacts/model/999999999',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'Artifact does not exist.')

    @patch('src.api.app.authenticate', return_value=True)
    def test_retrieve_invalid_artifact_type(self, mock_auth):
        """Test GET /artifacts/{invalid_type}/{id} returns 400"""
        response = self.client.get(
            '/artifacts/invalid_type/123',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('missing field', data['description'].lower())

    @patch('src.api.app.authenticate', return_value=True)
    def test_retrieve_invalid_id_format(self, mock_auth):
        """Test GET /artifacts/model/{invalid_id} returns 400"""
        response = self.client.get(
            '/artifacts/model/not-a-number',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 400)

    @patch('src.api.app.authenticate', return_value=False)
    def test_retrieve_authentication_failed(self, mock_auth):
        """Test GET /artifacts/model/{id} fails with invalid authentication"""
        response = self.client.get(
            '/artifacts/model/123',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 403)


class TestArtifactUpdateEndpoint(TestAPIEndpoints):
    """Test /artifacts/{artifact_type}/{id} PUT endpoint"""

    @patch('src.api.app.authenticate', return_value=True)
    def test_update_model_success(self, mock_auth):
        """Test PUT /artifacts/model/{id} updates existing model"""
        # Create a model first
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']
        
        # Update the model
        update_payload = {
            'metadata': {'name': 'whisper-tiny', 'custom_field': 'updated_value'},
            'data': {'url': 'https://huggingface.co/openai/whisper-tiny/tree/v2'}
        }
        response = self.client.put(
            f'/artifacts/model/{artifact_id}',
            headers=self.headers,
            data=json.dumps(update_payload)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'Artifact is updated.')
        
        # Verify the update
        self.assertEqual(model_registry[artifact_id].metadata['custom_field'], 'updated_value')
        self.assertEqual(model_registry[artifact_id].url, 'https://huggingface.co/openai/whisper-tiny/tree/v2')

    @patch('src.api.app.authenticate', return_value=True)
    def test_update_model_not_found(self, mock_auth):
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
        self.assertEqual(data['description'], 'Artifact does not exist.')

    @patch('src.api.app.authenticate', return_value=True)
    def test_update_invalid_artifact_type(self, mock_auth):
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

    @patch('src.api.app.authenticate', return_value=False)
    def test_update_authentication_failed(self, mock_auth):
        """Test PUT /artifacts/model/{id} fails with invalid authentication"""
        update_payload = {
            'metadata': {'name': 'test'},
            'data': {'url': 'https://huggingface.co/test/model'}
        }
        response = self.client.put(
            '/artifacts/model/123',
            headers=self.headers,
            data=json.dumps(update_payload)
        )
        
        self.assertEqual(response.status_code, 403)


class TestArtifactsListEndpoint(TestAPIEndpoints):
    """Test /artifacts POST endpoint"""

    @patch('src.api.app.authenticate', return_value=True)
    def test_list_artifacts_success(self, mock_auth):
        """Test POST /artifacts lists artifacts matching query"""
        # Create multiple models
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
        query = {
            'name': '*',
            'types': ['model']
        }
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)

    @patch('src.api.app.authenticate', return_value=True)
    def test_list_artifacts_by_type(self, mock_auth):
        """Test POST /artifacts filters by artifact type"""
        # Create a model
        self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': 'https://huggingface.co/openai/whisper-tiny'})
        )
        
        # Query for datasets (should return empty)
        query = {
            'name': '*',
            'types': ['dataset']
        }
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 0)

    @patch('src.api.app.authenticate', return_value=True)
    def test_list_artifacts_missing_name(self, mock_auth):
        """Test POST /artifacts fails without name field"""
        query = {
            'types': ['model']
        }
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('missing field', data['description'].lower())

    @patch('src.api.app.authenticate', return_value=True)
    def test_list_artifacts_missing_types(self, mock_auth):
        """Test POST /artifacts fails without types field"""
        query = {
            'name': '*'
        }
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('missing field', data['description'].lower())

    @patch('src.api.app.authenticate', return_value=False)
    def test_list_artifacts_authentication_failed(self, mock_auth):
        """Test POST /artifacts fails with invalid authentication"""
        query = {
            'name': '*',
            'types': ['model']
        }
        response = self.client.post(
            '/artifacts',
            headers=self.headers,
            data=json.dumps(query)
        )
        
        self.assertEqual(response.status_code, 403)


class TestModelArtifactRate(TestAPIEndpoints):
    """Test /artifact/model/{id}/rate endpoint and edge cases"""

    @patch('src.api.app.authenticate', return_value=True)
    @patch('src.api.app.validate_ndjson', return_value=True)
    @patch('src.api.app.handle_url')
    def test_model_rate_success(self, mock_handle, mock_validate, mock_auth):
        """Test GET /artifact/model/{id}/rate successfully computes and returns ndjson"""
        # prepare mocks
        raw_ndjson = {'metric_a': 0.9}
        mock_handle.return_value = [raw_ndjson]

        # create model
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']

        # request rating
        response = self.client.get(f'/artifact/model/{artifact_id}/rate', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # returned payload should include the computed metrics and name/category added by the endpoint
        self.assertIn('metric_a', data)
        self.assertEqual(data['metric_a'], 0.9)
        self.assertEqual(data['name'], 'whisper-tiny')
        self.assertEqual(data['category'], 'model')

    @patch('src.api.app.authenticate', return_value=True)
    @patch('src.api.app.handle_url', side_effect=Exception('hf error'))
    def test_model_rate_handle_url_error(self, mock_handle, mock_auth):
        """If the underlying rating code errors, endpoint should return 500"""
        # create model
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']

        response = self.client.get(f'/artifact/model/{artifact_id}/rate', headers=self.headers)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('description', data)
        self.assertIn('The artifact rating system encountered an error', data['description'])

    @patch('src.api.app.authenticate', return_value=True)
    @patch('src.api.app.validate_ndjson', return_value=False)
    @patch('src.api.app.handle_url')
    def test_model_rate_validation_fails_returns_empty(self, mock_handle, mock_validate, mock_auth):
        """If validation fails, the endpoint should return the still-empty ndjson (200 with empty dict)"""
        mock_handle.return_value = [{'bad': 'data'}]

        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']

        response = self.client.get(f'/artifact/model/{artifact_id}/rate', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # since validation failed, the model.ndjson remains empty
        self.assertEqual(data, {})

    @patch('src.api.app.authenticate', return_value=True)
    def test_model_rate_artifact_not_found(self, mock_auth):
        """Requesting rating for non-existent artifact returns 404"""
        response = self.client.get('/artifact/model/999999999/rate', headers=self.headers)
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'Artifact does not exist.')

    @patch('src.api.app.authenticate', return_value=True)
    @patch('src.api.app.handle_url')
    @patch('src.api.app.validate_ndjson')
    def test_model_rate_already_computed_skips_processing(self, mock_validate, mock_handle, mock_auth):
        """If ndjson already present on the artifact, the endpoint should return it and not call handle_url/validate"""
        # create model
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']

        # pre-populate ndjson
        model_registry[artifact_id].ndjson = {'pre': 'value'}

        response = self.client.get(f'/artifact/model/{artifact_id}/rate', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data, {'pre': 'value'})
        mock_handle.assert_not_called()
        mock_validate.assert_not_called()

    @patch('src.api.app.authenticate', return_value=False)
    def test_model_rate_authentication_failed(self, mock_auth):
        """Authentication failure returns 403"""
        response = self.client.get('/artifact/model/123/rate', headers=self.headers)
        self.assertEqual(response.status_code, 403)
class TestEdgeCases(TestAPIEndpoints):
    """Test edge cases and error handling"""

    @patch('src.api.app.authenticate', return_value=True)
    def test_multiple_models_same_name_different_urls(self, mock_auth):
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
        self.assertNotEqual(data1['id'], data2['id'])
        
        # Names should be the same
        self.assertEqual(data1['name'], data2['name'])

    @patch('src.api.app.authenticate', return_value=True)
    def test_retrieve_wrong_artifact_type(self, mock_auth):
        """Test retrieving with wrong artifact type returns 404"""
        # Create a model
        test_url = "https://huggingface.co/openai/whisper-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        created_data = json.loads(create_response.data)
        artifact_id = created_data['id']
        
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
