"""
WSGI config for QR_Backend project for PythonAnywhere deployment.

This file is used by PythonAnywhere to serve your Django application.
"""

import os
import sys

# Add your project directory to the Python path
path = '/home/urqrplate/QRPlate/QR_Backend'
if path not in sys.path:
    sys.path.insert(0, path)

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'QR_Backend.settings')

# Import Django's WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

