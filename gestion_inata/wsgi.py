"""
WSGI config for gestion_inata project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

settings_module = 'gestion_inata.deploiment_settings' if 'RENDER_EXTERNAL_HOSTNAME' in os.environ else 'gestion_inata.deploiment_settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_inata.settings')

application = get_wsgi_application()
