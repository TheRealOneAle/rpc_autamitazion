import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'publisher',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

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

# RabbitMQ
RABBIT_HOST = os.environ.get('RABBIT_HOST', 'rabbitmq')
RABBIT_USER = os.environ.get('RABBIT_USER', 'rpc')
RABBIT_PASS = os.environ.get('RABBIT_PASS', 'rpc1234')
RABBIT_EXCHANGE = 'rpc.events'
RABBIT_ROUTING_KEY = 'ranking.published'
CLOUDAMQP_URL = os.environ.get('CLOUDAMQP_URL', '')

# Service URLs
MS1_URL = os.environ.get('MS1_URL', 'http://ms1-connector:8001')
MS2_URL = os.environ.get('MS2_URL', 'http://ms2-renderer:8002')
