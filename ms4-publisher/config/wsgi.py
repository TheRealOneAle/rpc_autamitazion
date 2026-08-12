"""
WSGI config for ms4-publisher project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

from config.middleware import PrefixMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = PrefixMiddleware(
    get_wsgi_application(),
    prefix=getattr(settings, 'FORCE_SCRIPT_NAME', ''),
)
