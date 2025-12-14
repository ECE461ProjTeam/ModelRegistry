from .test_api_endpoints import TestAPIEndpoints
import json
from src.api.models import Artifact
from flask_sqlalchemy import SQLAlchemy

db  = SQLAlchemy()

class TestSensitiveModelUpload(TestAPIEndpoints):
    def test_create_sensitive_model_success(self):
        """Test POST /artifact/model creates a new model artifact"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url, 'sensitive': True, 'js_program': "console.log(\"Exiting normally...\");\nprocess.exit(0);"}
        
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
            
    def test_create_sensitive_missing_js_program(self):
        """Test POST /artifact/model with missing js-program field"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url, 'sensitive': True}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Sensitive artifact must include a js_program field.')

class TestSensitiveModelDownload(TestAPIEndpoints):
    def test_get_sensitive_model_success(self):
        """Test GET /artifact/model/{id} retrieves a model artifact"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url, 'sensitive': True, 'js_program': "console.log(\"Exiting normally...\");\nprocess.exit(0);"}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        metadata = data['metadata']
        model_id = metadata['id']
        
        model = Artifact.query.filter_by(id=model_id).first()
        model.download_url = "https://example.com/whisper-tiny"
        old_history = model.download_history
        db.session.commit()
        
        response = self.client.get(
            f'/artifacts/model/{model_id}',
            headers=self.headers
        )
        
        model = Artifact.query.filter_by(id=model_id).first()
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('metadata', data)
        self.assertIn('data', data)
        self.assertIn('stdout', data)
        self.assertEqual(data['stdout'], 'Exiting normally...\n')
        metadata = data['metadata']
        self.assertIn('name', metadata)
        self.assertIn('id', metadata)
        self.assertIn('type', metadata)
        self.assertEqual(metadata['name'], 'whisper-tiny')
        self.assertEqual(metadata['type'], 'model')
        self.assertIn('download_url', data['data'])
        self.assertNotEqual(data['data']['download_url'], "")
        self.assertEqual(len(old_history) + 1, len(model.download_history))
        
    def test_get_sensitive_model_failed_js(self):
        """Test GET /artifact/model/{id} with failed JS execution"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url, 'sensitive': True, 'js_program': "console.error(\"Error occurred...\");\nprocess.exit(1);"}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        metadata = data['metadata']
        model_id = metadata['id']
        
        model = Artifact.query.filter_by(id=model_id).first()
        model.download_url = "https://example.com/whisper-tiny"
        old_history = model.download_history
        db.session.commit()
        
        response = self.client.get(
            f'/artifacts/model/{model_id}',
            headers=self.headers
        )
        
        model = Artifact.query.filter_by(id=model_id).first()
        
        self.assertEqual(response.status_code, 202)
        data = json.loads(response.data)
        self.assertEqual(data["message"], "JS program returned non-zero exit code")
        self.assertEqual(data["data"]["download_url"], "")
        self.assertEqual(len(old_history), len(model.download_history))
        
    def test_get_sensitive_model_timeout(self):
        """Test GET / //model/{id} with JS program timeout"""
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'name': 'whisper-tiny', 'url': test_url, 'sensitive': True, 'js_program': "while(true) {}"}
        
        response = self.client.post(
            '/artifact/model',
            headers=self.headers,
            data=json.dumps(payload)
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        metadata = data['metadata']
        model_id = metadata['id']
        
        model = Artifact.query.filter_by(id=model_id).first()
        model.download_url = "https://example.com/whisper-tiny"
        old_history = model.download_history
        db.session.commit()
        
        response = self.client.get(
            f'/artifacts/model/{model_id}',
            headers=self.headers
        )
        
        model = Artifact.query.filter_by(id=model_id).first()
        
        self.assertEqual(response.status_code, 203)
        data = json.loads(response.data)
        self.assertEqual(data["message"], "JS program timed out")
        self.assertEqual(data["data"]["download_url"], "")
        self.assertEqual(len(old_history), len(model.download_history))
                