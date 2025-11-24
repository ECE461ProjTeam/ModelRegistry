"""Tests for authentication endpoints in `src/api/auth.py`.

These tests exercise the public endpoints implemented in the
authentication blueprint: authenticate, register, profile (GET/DELETE).

They create JWTs with the shape the endpoints expect (identity as a
dict with keys "name" and "is_admin") and use the Flask test client
to call the endpoints.
"""

import json
import unittest
from unittest.mock import patch
from src.api.app import app
from src.api.models import User, Artifact
from src.api.extensions import db
import os
from dotenv import load_dotenv
load_dotenv()


class TestAuthenticationEndpoints(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True
        # Push an application context so helpers like create_access_token
        # and DB operations that rely on current_app work inside tests.
        self._ctx = self.app.app_context()
        self._ctx.push()

    def tearDown(self):
        # Remove any non-default users created during tests
        # keep the default admin user, remove others
        User.query.filter(User.name != os.environ.get("DEFAULT_USER")).delete()
        db.session.commit()
        # Pop the application context we pushed in setUp
        self._ctx.pop()

    def test_authenticate_success(self):
        """PUT /authenticate should return a token for valid credentials."""
        payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": os.environ.get("DEFAULT_PASSWORD")}
        }

        resp = self.client.put('/authenticate', json=payload)
        self.assertEqual(resp.status_code, 200)
        token = resp.get_json()
        self.assertTrue(token)

    def test_authenticate_invalid_password(self):
        payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": "wrong-password"}
        }

        resp = self.client.put('/authenticate', json=payload)
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn('error', data)

    def test_get_profile_with_valid_token(self):
        """GET /profile should return the user's profile when JWT is valid.

        The endpoints expect the JWT identity to be a mapping with keys
        "name" and "is_admin" so we construct the token that way.
        """
        # obtain a real token via the authenticate endpoint so token format
        # matches what the app issues and what the middleware expects.
        auth_payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": os.environ.get("DEFAULT_PASSWORD")}
        }
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}

        resp = self.client.get('/profile', headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('profile', data)
        profile = data['profile']
        self.assertEqual(profile['name'], os.environ.get("DEFAULT_USER"))
        self.assertTrue(profile['is_admin'])
        self.assertIn('request_count', profile)

    def test_register_forbidden_for_non_admin(self):
        """POST /register should be forbidden for non-admin identities."""
        # create the non-admin user in the DB and authenticate to get a token
        with self.app.app_context():
            u = User(name='someuser', is_admin=False)
            u.set_password('pw')
            db.session.add(u)
            db.session.commit()

        auth_payload = {"user": {"name": 'someuser'}, "secret": {"password": 'pw'}}
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}

        payload = {
            "user": {"name": "newuser", "is_admin": False, "permissions": ["search"]},
            "secret": {"password": "pw"}
        }

        resp = self.client.post('/register', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn('error', data)

    def test_register_success_as_admin(self):
        """Admin can register a new user via POST /register."""
        auth_payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": os.environ.get("DEFAULT_PASSWORD")}
        }
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}

        payload = {
            "user": {"name": "testcreated", "is_admin": False, "permissions": ["search"]},
            "secret": {"password": "testpw123"}
        }

        resp = self.client.post('/register', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn('message', data)

        # ensure user exists in DB
        with self.app.app_context():
            u = User.query.filter_by(name='testcreated').first()
            self.assertIsNotNone(u)

    def test_delete_profile_as_owner(self):
        """A user may delete their own profile via DELETE /profile."""
        # create a user directly in the DB
        with self.app.app_context():
            u = User(name='tobedeleted', is_admin=False)
            u.set_password('deletepw')
            db.session.add(u)
            db.session.commit()
        # obtain token by authenticating as the newly created user
        auth_payload = {"user": {"name": 'tobedeleted'}, "secret": {"password": 'deletepw'}}
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}
        payload = {"user": {"name": 'tobedeleted'}}

        resp = self.client.delete('/profile', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('message', data)

        # verify user removed
        with self.app.app_context():
            u2 = User.query.filter_by(name='tobedeleted').first()
            self.assertIsNone(u2)

    def test_delete_profile_as_admin(self):
        """An admin may delete another user's profile via DELETE /profile."""
        # create a user directly in the DB to be deleted
        with self.app.app_context():
            u = User(name='otheruser', is_admin=False)
            u.set_password('otherpw')
            db.session.add(u)
            db.session.commit()

        # admin token (get via authenticate endpoint)
        auth_payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": os.environ.get("DEFAULT_PASSWORD")}
        }
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}
        payload = {"user": {"name": 'otheruser'}}

        resp = self.client.delete('/profile', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('message', data)

        # verify user removed
        with self.app.app_context():
            u2 = User.query.filter_by(name='otheruser').first()
            self.assertIsNone(u2)

class TestPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch_clear = patch('src.api.app.clear_s3_bucket', return_value=None)
        cls.mock_clear = cls.patch_clear.start()
        
    @classmethod
    def tearDownClass(cls):
        cls.patch_clear.stop()
    
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True
        # Push an application context so helpers like create_access_token
        # and DB operations that rely on current_app work inside tests.
        self._ctx = self.app.app_context()
        self._ctx.push()

    def tearDown(self):
        # Remove any non-default users created during tests
        # keep the default admin user, remove others
        User.query.filter(User.name != os.environ.get("DEFAULT_USER")).delete()
        db.session.commit()
        # Pop the application context we pushed in setUp
        self._ctx.pop()

    def test_check_permissions_decorator_allowed(self):
        """Test that the check_permissions decorator allows access when permissions are present."""
        """Test that the check_permissions decorator allows access when permissions are present."""
        # Create a user with the required permission
        with self.app.app_context():
            u = User(name='permuser', is_admin=False, permissions=['search', 'upload'])
            u.set_password('permpw')
            db.session.add(u)
            db.session.commit()

        # Authenticate as the user to get a token
        auth_payload = {"user": {"name": 'permuser'}, "secret": {"password": 'permpw'}}
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}", "Content-Type": "application/json"}

        # Create an Artifact
        test_url = "https://huggingface.co/openai/whisper-tiny"
        payload = {'url': test_url}
        response = self.client.post(
                    '/artifact/model',
                    headers=headers,
                    data=json.dumps(payload)
                )
        self.assertEqual(response.status_code, 201)

    def test_check_permissions_decorator_denied(self):
        """Test that the check_permissions decorator denies access when permissions are missing."""
        # Create a user without the required permission
        with self.app.app_context():
            u = User(name='nopermuser', is_admin=False, permissions=['other'])
            u.set_password('nopermpw')
            db.session.add(u)
            db.session.commit()

        # Authenticate as the user to get a token
        auth_payload = {"user": {"name": 'nopermuser'}, "secret": {"password": 'nopermpw'}}
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}

        # Access the protected route with a valid artifact query
        payload = {"name": "whisper-tiny", "types": ["model"]}
        resp = self.client.post('/artifacts', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 401)
        
    def test_check_permissions_decorator_admin(self):
        """Test that admin users bypass permission checks in the check_permissions decorator."""
        # Authenticate as the default admin user to get a token
        auth_payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": os.environ.get("DEFAULT_PASSWORD")}
        }
        auth_resp = self.client.put('/authenticate', json=auth_payload)
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.get_json()
        headers = {"X-Authorization": f"{token}"}

        # Access the protected route
        resp = self.client.delete('/reset', headers=headers)
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
