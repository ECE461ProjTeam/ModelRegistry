"""Tests for authentication endpoints in `src/api/auth.py`.

These tests exercise the public endpoints implemented in the
authentication blueprint: authenticate, register, profile (GET/DELETE).

They create JWTs with the shape the endpoints expect (identity as a
dict with keys "name" and "is_admin") and use the Flask test client
to call the endpoints.
"""

import unittest
from src.api.app import app
from src.api.models import User
from src.api.extensions import db
from flask_jwt_extended import create_access_token
import os
from dotenv import load_dotenv
load_dotenv()

class TestAuthenticationEndpoints(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True

    def tearDown(self):
        # Remove any non-default users created during tests
        with self.app.app_context():
            # keep the default admin user, remove others
            User.query.filter(User.name != os.environ.get("DEFAULT_USER")).delete()
            db.session.commit()

    def test_authenticate_success(self):
        """PUT /authenticate should return a token for valid credentials."""
        payload = {
            "user": {"name": os.environ.get("DEFAULT_USER")},
            "secret": {"password": os.environ.get("DEFAULT_PASSWORD")}
        }

        resp = self.client.put('/authenticate', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('token', data)

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
        token = create_access_token(identity={"name": os.environ.get("DEFAULT_USER"), "is_admin": True})
        headers = {"Authorization": f"Bearer {token}"}

        resp = self.client.get('/profile', headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('profile', data)
        profile = data['profile']
        self.assertEqual(profile['name'], os.environ.get("DEFAULT_USER"))
        self.assertTrue(profile['is_admin'])
        self.assertIn('request_count', profile)
        self.assertIn('last_reset', profile)

    def test_register_forbidden_for_non_admin(self):
        """POST /register should be forbidden for non-admin identities."""
        token = create_access_token(identity={"name": "someuser", "is_admin": False})
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "user": {"name": "newuser", "is_admin": False},
            "secret": {"password": "pw"}
        }

        resp = self.client.post('/register', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIn('error', data)

    def test_register_success_as_admin(self):
        """Admin can register a new user via POST /register."""
        token = create_access_token(identity={"name": os.environ.get("DEFAULT_USER"), "is_admin": True})
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "user": {"name": "testcreated", "is_admin": False},
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

        token = create_access_token(identity={"name": 'tobedeleted', "is_admin": False})
        headers = {"Authorization": f"Bearer {token}"}
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

        # admin token
        token = create_access_token(identity={"name": os.environ.get("DEFAULT_USER"), "is_admin": True})
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"user": {"name": 'otheruser'}}

        resp = self.client.delete('/profile', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('message', data)

        # verify user removed
        with self.app.app_context():
            u2 = User.query.filter_by(name='otheruser').first()
            self.assertIsNone(u2)


if __name__ == '__main__':
    unittest.main()
