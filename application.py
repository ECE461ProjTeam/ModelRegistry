"""
Top-level entrypoint required for AWS Elastic Beanstalk deployments.

Elastic Beanstalk's Python platform (and many WSGI servers) expects a
top-level module that exposes a WSGI application callable named
``application``. This file re-exports the Flask app defined in
``src.api.app`` as ``application`` so the EB runtime can discover and
serve the app without changing the project's package layout.
"""

from src.api.app import app as application
