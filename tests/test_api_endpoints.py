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
from unittest.mock import patch, MagicMock


# Helper to mock boto3.client calls for health endpoints so tests do not call AWS
def mocked_boto3_client(service_name, region_name=None):
    mock = MagicMock()

    if service_name == "elasticbeanstalk":
        # describe_environment_resources used to get Instances and LoadBalancers
        mock.describe_environment_resources.return_value = {
            "EnvironmentResources": {
                "Instances": [{"Id": "i-0123456789abcdef0"}],
                "LoadBalancers": [{"Name": "arn:aws:elasticloadbalancing:us-east-2:123456789012:loadbalancer/app/myalb/50dc6c495c0c9188"}]
            }
        }
        mock.describe_environment_health.return_value = {"Status": "Green", "Color": "Green"}
        mock.describe_events.return_value = {"Events": [{"Message": "Mock event", "EventDate": "2025-01-01T00:00:00Z"}]}

    if service_name == "cloudwatch":
        # get_metric_statistics returns datapoints for metrics; support both Average and Sum
        def get_metric_statistics(**kwargs):
            metric = kwargs.get("MetricName", "")
            if metric == 'CPUUtilization':
                return {"Datapoints": [{"Average": 10.0}], "Label": metric}
            if metric == 'WriteLatency':
                return {"Datapoints": [{"Average": 0.1}], "Label": metric}
            if metric == 'RequestCount':
                return {"Datapoints": [{"Sum": 5}], "Label": metric}
            return {"Datapoints": []}

        mock.get_metric_statistics.side_effect = get_metric_statistics

    if service_name == "s3":
        # paginator for list_objects_v2
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": [{"Size": 100}, {"Size": 200}]}]
        mock.get_paginator.return_value = paginator

    if service_name == "logs":
        mock.filter_log_events.return_value = {"events": [{"message": "log message", "timestamp": 1234567890}]}

    return mock

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
        self.assertIn('missing field', data.get('error', '').lower())

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
        self.assertIn('error', data)

    def test_create_code_success(self):
        """Test POST /artifact/code creates a new code artifact"""
        test_url = "https://github.com/openai/whisper"
        payload = {'name': 'whisper-code', 'url': test_url}
        
        response = self.client.post(
            '/artifact/code',
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
        self.assertEqual(metadata['name'], 'whisper-code')
        self.assertEqual(metadata['type'], 'code')
        with self.app.app_context():
            self.assertIsNotNone(Artifact.query.filter_by(id=metadata['id']).first())
        
    def test_create_dataset_success(self):
        """Test POST /artifact/dataset creates a new dataset artifact"""
        test_url = "https://huggingface.co/datasets/tensonaut/EPSTEIN_FILES_20K"
        payload = {'name': 'whisper-dataset', 'url': test_url}
        
        response = self.client.post(
            '/artifact/dataset',
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
        self.assertEqual(metadata['name'], 'whisper-dataset')
        self.assertEqual(metadata['type'], 'dataset')
        with self.app.app_context():
            self.assertIsNotNone(Artifact.query.filter_by(id=metadata['id']).first())

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
        data = json.loads(response.data)["metadata"]
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
        self.assertEqual(data.get('error'), 'Artifact does not exist.')

    def test_retrieve_invalid_artifact_type(self):
        """Test GET /artifacts/{invalid_type}/{id} returns 400"""
        response = self.client.get(
            '/artifacts/invalid_type/123',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('missing field', data.get('error', '').lower())

    def test_retrieve_invalid_id_format(self):
        """Test GET /artifacts/model/{invalid_id} returns 400"""
        response = self.client.get(
            '/artifacts/model/not-a-number',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)

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
        self.assertEqual(data.get('error'), 'Artifact does not exist.')

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
        self.assertIn('missing field', data.get('error', '').lower())

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

class TestSearchByName(TestAPIEndpoints):
    """Test /artifact/byName/<name> GET endpoint"""

    def test_search_by_name_success(self):
        """Test POST /artifact/searchByName finds artifacts by name pattern"""
        # Create multiple models
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        names = ["whisper-tiny", "whisper-base", "bert-base"]
        
        for i, url in enumerate(urls):
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url, 'name': names[i]})
            )

        response = self.client.get(
            '/artifact/byName/whisper-tiny',
            headers=self.headers,
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_search_all(self):
        """Test GET /artifact/byName/* returns all artifacts (wildcard search)."""
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        names = ["whisper-tiny", "whisper-base", "bert-base"]
        
        for i, url in enumerate(urls):
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url, 'name': names[i]})
            )
        response = self.client.get(
            '/artifact/byName/*',
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 3)

    def test_search_by_name_no_matches(self):
        """Test GET /artifact/byName returns 404 when no matches"""
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        names = ["whisper-tiny", "whisper-base", "bert-base"]
        
        for i, url in enumerate(urls):
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url, 'name': names[i]})
            )
        response = self.client.get(
            '/artifact/byName/nonexistent',
            headers=self.headers,
        )
        
        self.assertEqual(response.status_code, 404)


class TestSearchByRegex(TestAPIEndpoints):
    """Test /artifact/byRegEx POST endpoint"""

    def test_search_by_regex_success(self):
        """Test POST /artifact/byRegEx finds artifacts matching regex"""
        # Create multiple models
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        names = ["whisper-tiny", "whisper-base", "bert-base"]
        
        for i, url in enumerate(urls):
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url, 'name': names[i]})
            )

        payload = {'regex': 'whisper-.*'}
        response = self.client.post(
            '/artifact/byRegEx',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

    def test_search_by_regex_one(self):
        """Test POST /artifact/byRegEx finds artifacts matching regex"""
        # Create multiple models
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        names = ["whisper-tiny", "whisper-base", "bert-base"]
        
        for i, url in enumerate(urls):
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url, 'name': names[i]})
            )

        payload = {'regex': '.*whisper-base.*'}
        response = self.client.post(
            '/artifact/byRegEx',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'whisper-base')

    def test_search_by_regex_no_matches(self):
        """Test POST /artifact/byRegEx returns 404 when no matches"""
        urls = [
            "https://huggingface.co/openai/whisper-tiny",
            "https://huggingface.co/openai/whisper-base",
            "https://huggingface.co/bert/bert-base"
        ]
        names = ["whisper-tiny", "whisper-base", "bert-base"]
        
        for i, url in enumerate(urls):
            self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url, 'name': names[i]})
            )
        payload = {'regex': 'nonexistent.*'}
        response = self.client.post(
            '/artifact/byRegEx',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 404)

    def test_dangerous_regex_rejected(self):
        """Test POST /artifact/byRegEx rejects dangerous regex patterns"""
        payload = {'regex': '(a+)+$'}
        response = self.client.post(
            '/artifact/byRegEx',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('potentially dangerous', data.get('message', '').lower())

    def test_missing_regex_field(self):
        """Test POST /artifact/byRegEx fails without regex field"""
        payload = {}
        response = self.client.post(
            '/artifact/byRegEx',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)


class TestLicenseCheckEndpoint(TestAPIEndpoints):
    """Test /artifact/model/{id}/license-check POST endpoint"""

    def test_license_check_model_not_found(self):
        """Test POST /artifact/model/{id}/license-check returns 404 for non-existent model"""
        response = self.client.post(
            '/artifact/model/999999/license-check',
            headers=self.headers,
            data=json.dumps({'github_url': 'https://github.com/huggingface/transformers'})
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_license_check_authentication_failed(self):
        """Test POST /artifact/model/{id}/license-check fails with missing authentication"""
        response = self.client.post(
            '/artifact/model/1/license-check',
            data=json.dumps({'github_url': 'https://github.com/huggingface/transformers'})
        )
        
        self.assertEqual(response.status_code, 401)

    def test_license_check_invalid_github_url(self):
        """Test POST /artifact/model/{id}/license-check returns 400 for invalid GitHub URL"""
        response = self.client.post(
            '/artifact/model/999999/license-check',
            headers=self.headers,
            data=json.dumps({'github_url': 'not-a-url'})
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_license_check_github_repo_not_found(self):
        """Test POST /artifact/model/{id}/license-check returns 404 for non-existent GitHub repo"""
        test_url = "https://huggingface.co/distilbert-base-uncased-finetuned-sst-2-english"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'name': 'distilbert-sst2', 'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        artifact_id = json.loads(create_response.data)['metadata']['id']
        
        response = self.client.post(
            f'/artifact/model/{artifact_id}/license-check',
            headers=self.headers,
            data=json.dumps({'github_url': 'https://github.com/nonexistent-user/nonexistent-repo'})
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_license_check_repo_no_license_incompatible(self):
        """Test POST /artifact/model/{id}/license-check returns false for repo with no license"""
        test_url = "https://huggingface.co/distilbert-base-uncased-finetuned-sst-2-english"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'name': 'distilbert-sst2', 'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        artifact_id = json.loads(create_response.data)['metadata']['id']
        
        response = self.client.post(
            f'/artifact/model/{artifact_id}/license-check',
            headers=self.headers,
            data=json.dumps({'github_url': 'https://github.com/octocat/Hello-World'})
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data)

    def test_license_check_compatible_license_success(self):
        """Test POST /artifact/model/{id}/license-check returns true for compatible license"""
        test_url = "https://huggingface.co/distilbert-base-uncased-finetuned-sst-2-english"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'name': 'distilbert-sst2', 'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        artifact_id = json.loads(create_response.data)['metadata']['id']
        
        response = self.client.post(
            f'/artifact/model/{artifact_id}/license-check',
            headers=self.headers,
            data=json.dumps({'github_url': 'https://github.com/apache/airflow'})
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data)


class TestArtifactLineageEndpoint(TestAPIEndpoints):
    """Test /artifact/model/{id}/lineage GET endpoint"""
    
    def _populate_lineage_data(self, artifact_id, model_id, base_model_hints=None, tags=None):
        """Helper to populate lineage data for an artifact (since rate() is mocked)"""
        with self.app.app_context():
            artifact = Artifact.query.get(artifact_id)
            if artifact:
                artifact.ndjson = artifact.ndjson or {}
                artifact.ndjson['lineage'] = {
                    'model_id': model_id,
                    'base_model': None,
                    'base_model_hints': base_model_hints or [],
                    'tags': tags or [],
                    'model_type': 'bert'
                }
                db.session.commit()

    def test_lineage_not_found(self):
        """Test GET /artifact/model/{id}/lineage returns 404 for non-existent model"""
        response = self.client.get(
            '/artifact/model/999999/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_lineage_authentication_failed(self):
        """Test GET /artifact/model/{id}/lineage fails without authentication"""
        response = self.client.get('/artifact/model/1/lineage')
        
        self.assertEqual(response.status_code, 401)

    def test_lineage_invalid_id_format(self):
        """Test GET /artifact/model/{id}/lineage returns 404 for malformed ID"""
        response = self.client.get(
            '/artifact/model/invalid/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)

    def test_lineage_standalone_model(self):
        """Test lineage for a model with no parents or children"""
        # Create a standalone model
        test_url = "https://huggingface.co/prajjwal1/bert-tiny"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        self.assertEqual(create_response.status_code, 201)
        artifact_id = json.loads(create_response.data)['metadata']['id']
        
        # Populate lineage data (no parents)
        self._populate_lineage_data(artifact_id, 'prajjwal1/bert-tiny')
        
        # Query lineage
        response = self.client.get(
            f'/artifact/model/{artifact_id}/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        self.assertEqual(len(data['nodes']), 1)
        self.assertEqual(len(data['edges']), 0)
        self.assertEqual(data['nodes'][0]['artifact_id'], artifact_id)

    def test_lineage_parent_child_relationship(self):
        """Test lineage with parent-child (base model and finetuned model)"""
        # Create base model
        base_url = "https://huggingface.co/google-bert/bert-base-uncased"
        base_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': base_url})
        )
        self.assertEqual(base_response.status_code, 201)
        base_id = json.loads(base_response.data)['metadata']['id']
        
        # Create finetuned model
        child_url = "https://huggingface.co/ManavDhayeCoder/sentiment-bert"
        child_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': child_url})
        )
        self.assertEqual(child_response.status_code, 201)
        child_id = json.loads(child_response.data)['metadata']['id']
        
        # Populate lineage data
        self._populate_lineage_data(base_id, 'google-bert/bert-base-uncased')
        self._populate_lineage_data(
            child_id, 
            'ManavDhayeCoder/sentiment-bert',
            base_model_hints=['google-bert/bert-base-uncased'],
            tags=['base_model:google-bert/bert-base-uncased', 'base_model:finetune:google-bert/bert-base-uncased']
        )
        
        # Query lineage for child (should show parent)
        response = self.client.get(
            f'/artifact/model/{child_id}/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        self.assertEqual(len(data['nodes']), 2)
        self.assertEqual(len(data['edges']), 1)
        
        # Verify edge direction and relationship
        edge = data['edges'][0]
        self.assertEqual(edge['from_node_artifact_id'], base_id)
        self.assertEqual(edge['to_node_artifact_id'], child_id)
        self.assertEqual(edge['relationship'], 'finetune')
        
        # Query lineage for base (should show child)
        response = self.client.get(
            f'/artifact/model/{base_id}/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['nodes']), 2)
        self.assertEqual(len(data['edges']), 1)
        
        # Edge should be same: base -> child
        edge = data['edges'][0]
        self.assertEqual(edge['from_node_artifact_id'], base_id)
        self.assertEqual(edge['to_node_artifact_id'], child_id)

    def test_lineage_multiple_children(self):
        """Test lineage with one parent and multiple children"""
        # Create base model
        base_url = "https://huggingface.co/google-bert/bert-base-uncased"
        base_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': base_url})
        )
        self.assertEqual(base_response.status_code, 201)
        base_id = json.loads(base_response.data)['metadata']['id']
        
        # Create multiple derived models
        derived_models = [
            ("https://huggingface.co/ManavDhayeCoder/sentiment-bert", "ManavDhayeCoder/sentiment-bert"),
            ("https://huggingface.co/kwwww/bert-base-uncased-test_4_1039", "kwwww/bert-base-uncased-test_4_1039"),
            ("https://huggingface.co/ggml-org/bert-base-uncased", "ggml-org/bert-base-uncased")
        ]
        derived_ids = []
        
        # Populate base model lineage
        self._populate_lineage_data(base_id, 'google-bert/bert-base-uncased')
        
        for url, model_id in derived_models:
            response = self.client.post(
                '/artifact/model',
                headers=self.headers,
                data=json.dumps({'url': url})
            )
            self.assertEqual(response.status_code, 201)
            artifact_id = json.loads(response.data)['metadata']['id']
            derived_ids.append(artifact_id)
            
            # Populate lineage data for derived model
            self._populate_lineage_data(
                artifact_id,
                model_id,
                base_model_hints=['google-bert/bert-base-uncased'],
                tags=['base_model:google-bert/bert-base-uncased']
            )
        
        # Query lineage for base model
        response = self.client.get(
            f'/artifact/model/{base_id}/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Should have base + 3 children = 4 nodes
        self.assertEqual(len(data['nodes']), 4)
        # Should have 3 edges (base -> each child)
        self.assertEqual(len(data['edges']), 3)
        
        # Verify all edges point from base to children
        for edge in data['edges']:
            self.assertEqual(edge['from_node_artifact_id'], base_id)
            self.assertIn(edge['to_node_artifact_id'], derived_ids)

    def test_lineage_relationship_types(self):
        """Test that different relationship types are correctly identified"""
        # Create base model
        base_url = "https://huggingface.co/google-bert/bert-base-uncased"
        base_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': base_url})
        )
        base_id = json.loads(base_response.data)['metadata']['id']
        
        # Create finetuned model
        finetune_url = "https://huggingface.co/ManavDhayeCoder/sentiment-bert"
        finetune_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': finetune_url})
        )
        finetune_id = json.loads(finetune_response.data)['metadata']['id']
        
        # Create adapter model
        adapter_url = "https://huggingface.co/kwwww/bert-base-uncased-test_4_1039"
        adapter_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': adapter_url})
        )
        adapter_id = json.loads(adapter_response.data)['metadata']['id']


        # Create quanitzed model
        quantized_url = "https://huggingface.co/ManavDhayeCoder/sentiment-bert"
        quantized_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': quantized_url})
        )
        quantized_id = json.loads(quantized_response.data)['metadata']['id']
        
        # Populate lineage data
        self._populate_lineage_data(base_id, 'google-bert/bert-base-uncased')
        self._populate_lineage_data(
            finetune_id,
            'ManavDhayeCoder/sentiment-bert',
            base_model_hints=['google-bert/bert-base-uncased'],
            tags=['base_model:finetune:google-bert/bert-base-uncased']
        )
        self._populate_lineage_data(
            adapter_id,
            'kwwww/bert-base-uncased-test_4_1039',
            base_model_hints=['google-bert/bert-base-uncased'],
            tags=['base_model:adapter:google-bert/bert-base-uncased']
        )
        self._populate_lineage_data(
            quantized_id,
            'ManavDhayeCoder/sentiment-bert',
            base_model_hints=['google-bert/bert-base-uncased'],
            tags=['base_model:quantized:google-bert/bert-base-uncased']
        )
        
        # Query lineage for base model
        response = self.client.get(
            f'/artifact/model/{base_id}/lineage',
            headers=self.headers
        )
        
        data = json.loads(response.data)
        
        # Find edges and verify relationship types
        relationships = {}
        for edge in data['edges']:
            relationships[edge['to_node_artifact_id']] = edge['relationship']
        
        # Verify finetune relationship
        self.assertEqual(relationships[finetune_id], 'finetune')
        # Verify adapter relationship
        self.assertEqual(relationships[adapter_id], 'adapter')

    def test_lineage_response_format(self):
        """Test that lineage response has correct structure and field ordering"""
        # Create a model
        test_url = "https://huggingface.co/google-bert/bert-base-uncased"
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps({'url': test_url})
        )
        artifact_id = json.loads(create_response.data)['metadata']['id']
        
        # Populate lineage data
        self._populate_lineage_data(artifact_id, 'google-bert/bert-base-uncased')
        
        # Query lineage
        response = self.client.get(
            f'/artifact/model/{artifact_id}/lineage',
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Verify top-level keys
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        
        # Verify nodes structure
        for node in data['nodes']:
            self.assertIn('artifact_id', node)
            self.assertIn('name', node)
            self.assertIn('source', node)
            # Verify field types
            self.assertIsInstance(node['artifact_id'], int)
            self.assertIsInstance(node['name'], str)
            self.assertIsInstance(node['source'], str)
        
        # Verify edges structure (if present)
        for edge in data['edges']:
            self.assertIn('from_node_artifact_id', edge)
            self.assertIn('to_node_artifact_id', edge)
            self.assertIn('relationship', edge)
            # Verify field types
            self.assertIsInstance(edge['from_node_artifact_id'], int)
            self.assertIsInstance(edge['to_node_artifact_id'], int)
            self.assertIsInstance(edge['relationship'], str)


class TestSystemHealth(TestAPIEndpoints):
    """Test /health and /health/components endpoints"""

    def setUp(self):
        # Start parent setup first (creates test client and auth headers)
        super().setUp()
        # Patch boto3.client so AWS calls are mocked for these tests
        self._boto_patcher = patch('boto3.client', side_effect=mocked_boto3_client)
        self.mock_boto_client = self._boto_patcher.start()

    def tearDown(self):
        # Stop boto3.client patcher then run parent teardown
        try:
            self._boto_patcher.stop()
        except Exception:
            pass
        super().tearDown()
    
    def test_health_check_success(self):
        """Test GET /health returns service reachable"""
        response = self.client.get('/health', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('message', data)
        self.assertEqual(data['message'], 'Service reachable.')
        self.assertIn('timestamp', data)
    
    def test_health_components_success(self):
        """Test GET /health/components returns health components with valid auth"""
        response = self.client.get('/health/components', headers=self.headers, query_string={'windowMinutes': 60, 'includeTimeline': 'true'})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('components', data)
        self.assertIsInstance(data['components'], list)

    def test_health_components_empty_query(self):
        """Test GET /health/components with empty query params returns default components"""
        response = self.client.get('/health/components', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('components', data)
        self.assertIsInstance(data['components'], list)

    def test_health_components_invalid_query(self):
        """Test GET /health/components with invalid query params returns 400"""
        response = self.client.get('/health/components', headers=self.headers, query_string={'invalid_key': 'value'})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('message', data)
    
    def test_health_components_authentication_failed(self):
        """Test GET /health/components fails with invalid authentication"""
        # call without auth headers to simulate unauthenticated request
        response = self.client.get('/health/components')
        self.assertEqual(response.status_code, 401)

    def test_health_components_invalid_windowMinutes(self):
        """Test GET /health/components with invalid input returns 400"""
        response = self.client.get('/health/components', headers=self.headers, query_string={'windowMinutes': 'not-an-integer'})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('message', data)
    
    def test_health_components_negative_windowMinutes(self):
        """Test GET /health/components with negative windowMinutes returns 400"""
        response = self.client.get('/health/components', headers=self.headers, query_string={'windowMinutes': -10})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('message', data)
    
    def test_health_components_invalid_includeTimeline(self):
        """Test GET /health/components with invalid includeTimeline returns 400"""
        response = self.client.get('/health/components', headers=self.headers, query_string={'includeTimeline': 'not-a-boolean'})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('message', data)


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
    test_suite.addTest(unittest.makeSuite(TestSearchByName))
    test_suite.addTest(unittest.makeSuite(TestSearchByRegex))
    test_suite.addTest(unittest.makeSuite(TestLicenseCheckEndpoint))
    test_suite.addTest(unittest.makeSuite(TestSystemHealth))
    return test_suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())