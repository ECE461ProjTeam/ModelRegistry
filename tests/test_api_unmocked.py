"""Integration tests for API endpoints without AWS mocks.

Performs end-to-end requests against the Flask test client using the real
application components (no mocked S3 or external services).
"""

import unittest
import json
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.app import app
from src.api.models import Artifact
from src.api.extensions import db

class TestAPIUnmocked(unittest.TestCase):
    """Test suite for Model Registry API endpoints"""

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
        
        
class TestUpload(TestAPIUnmocked):
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
        self.assertNotEqual(data['data']['download_url'], "")
        with self.app.app_context():
            self.assertIsNotNone(Artifact.query.filter_by(id=metadata['id']).first())
            
class TestRateEndpoint(TestAPIUnmocked):
    def test_rate_model_success(self):
        """Test POST /artifact/model/<id>/rate successfully rates a model artifact"""
        # First, create a model artifact to rate
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url}
        
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(create_response.status_code, 201)
        create_data = json.loads(create_response.data)
        model_id = create_data['metadata']['id']
        
        # Now, rate the created model artifact
        rate_response = self.client.get(
            f'/artifact/model/{model_id}/rate',
            headers=self.headers
        )
        
        self.assertEqual(rate_response.status_code, 200)
        rate_data = json.loads(rate_response.data)
        self.assertIn('net_score', rate_data)
        

class TestResetEndpoint(TestAPIUnmocked):  
    def test_reset_success_as_admin(self):
            """Test DELETE /reset successfully resets registry as admin"""
            # Reset the registry
            response = self.client.delete('/reset', headers=self.headers)
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            # app returns 'message' key for success responses
            self.assertEqual(data.get('message'), 'Registry is reset.')
            with self.app.app_context():
                self.assertEqual(Artifact.query.count(), 0)
                
class TestRegexSearchREADME(TestAPIUnmocked):
    def test_regex_search_readme_success(self):
        """Test POST /artifact/byRegEx successfully searches artifacts by regex in name and readme"""
        # First, create a model artifact with a specific readme
        test_url = "https://huggingface.co/openai/whisper-tiny"
        readme_content = "This is a test model for speech recognition."
        payload = {'name': 'whisper-tiny', 'url': test_url, 'readme': readme_content}
        
        create_response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(create_response.status_code, 201)
        
        # Now, search for the artifact using a regex that matches the readme content
        regex_payload = {'regex': '.*speech recognition.*'}
        
        search_response = self.client.post(
            '/artifact/byRegEx',
            headers=self.headers,
            data=json.dumps(regex_payload)
        )
        
        self.assertEqual(search_response.status_code, 200)
        search_data = json.loads(search_response.data)
        self.assertIsInstance(search_data, list)
        self.assertGreaterEqual(len(search_data), 1)
        found_names = [artifact['name'] for artifact in search_data]
        self.assertIn('whisper-tiny', found_names)