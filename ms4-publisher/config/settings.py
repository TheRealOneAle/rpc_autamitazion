import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
# Contexto bajo el cual vive la app tras el Nginx (ej. /facebook-table/publisher).
# Vacio = raiz del dominio (Render).
FORCE_SCRIPT_NAME = os.environ.get('FORCE_SCRIPT_NAME', '').rstrip('/')
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'http://localhost:8000',
    'http://localhost:8001',
    'http://localhost:8003',
]

# Login con Google (OAuth2)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
# URI de redireccion OAuth. Si no se define, se calcula desde el request.
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '')
# Whitelist de correos permitidos (separados por comas o dominios @ejemplo.com)
ALLOWED_EMAILS = [e.strip().lower() for e in os.environ.get('ALLOWED_EMAILS', '').split(',') if e.strip()]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'


# Nginx/Render reenvian X-Forwarded-Proto: https
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'rest_framework',
    'corsheaders',
    'publisher',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': ['publisher.context_processors.rpc_context']},
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

# Service URLs — Render pasa solo el host; se normaliza a https://
def _to_url(val, default):
    if not val:
        return default
    return val if val.startswith('http') else f'https://{val}'

MS1_URL = _to_url(os.environ.get('MS1_URL'), 'http://boca-scraper:3001')
MS2_URL = _to_url(os.environ.get('MS2_URL'), 'http://generartabla:5002')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'publisher': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apscheduler': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
