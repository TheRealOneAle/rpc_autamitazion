import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'http://localhost:8000',
]

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'corsheaders',
    'publisher',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': []},
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'ms4_publisher'),
        'USER': os.environ.get('POSTGRES_USER', 'rpc_user'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'rpc_pass'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_TZ = True

# RabbitMQ — si existe CLOUDAMQP_URL se parsea automáticamente
CLOUDAMQP_URL = os.environ.get('CLOUDAMQP_URL', '')
if CLOUDAMQP_URL:
    from urllib.parse import urlparse as _urlparse
    _amqp = _urlparse(CLOUDAMQP_URL)
    RABBIT_HOST = _amqp.hostname
    RABBIT_USER = _amqp.username
    RABBIT_PASS = _amqp.password
    RABBIT_VHOST = _amqp.path.lstrip('/')
else:
    RABBIT_HOST = os.environ.get('RABBIT_HOST', 'rabbitmq')
    RABBIT_USER = os.environ.get('RABBIT_USER', 'rpc')
    RABBIT_PASS = os.environ.get('RABBIT_PASS', 'rpc1234')
    RABBIT_VHOST = '/'
RABBIT_EXCHANGE = 'rpc.events'
RABBIT_ROUTING_KEY = 'ranking.published'

# Service URLs — Render pasa solo el host; se normaliza a https://
def _to_url(val, default):
    if not val:
        return default
    return val if val.startswith('http') else f'https://{val}'

MS1_URL = _to_url(os.environ.get('MS1_URL'), 'http://ms1-connector:8001')
MS2_URL = _to_url(os.environ.get('MS2_URL'), 'http://ms2-renderer:8002')
