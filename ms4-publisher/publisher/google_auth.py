import logging
import secrets
import requests
from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse

log = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPE = "openid email profile"


def _google_redirect_uri(request):
    if settings.GOOGLE_REDIRECT_URI:
        return settings.GOOGLE_REDIRECT_URI
    return request.build_absolute_uri(reverse('google_callback'))


def _seed_user_config(user):
    """Siembra la configuracion por defecto de un usuario (solo si no existe)."""
    from .models import UserConfig
    defaults = {
        'proceso_activo': 'true',
        'publication_text': '',
        'competition_name': '',
        'boca_year': '',
        'boca_contest': '',
        'activated_by': '',
    }
    for key, value in defaults.items():
        UserConfig.objects.get_or_create(user=user, key=key, defaults={'value': value})


def login_page(request):
    """Pagina de login. Si ya hay sesion, va directo al dashboard."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'publisher/login.html', {'error': request.GET.get('error', '')})


def google_login(request):
    """Inicia el flujo OAuth redirigiendo al usuario a Google."""
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        return HttpResponseBadRequest(
            "GOOGLE_CLIENT_ID no configurado. Agrega GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET al .env"
        )

    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state

    params = urlencode({
        'client_id': client_id,
        'redirect_uri': _google_redirect_uri(request),
        'state': state,
        'scope': SCOPE,
        'response_type': 'code',
    })
    url = f"{GOOGLE_AUTH_URL}?{params}"
    return HttpResponseRedirect(url)


def google_callback(request):
    """Canjea el code de Google por un token, crea/autentica al usuario y lo loguea."""
    error = request.GET.get('error')
    if error:
        return render(request, 'publisher/login.html', {
            'error': request.GET.get('error_description', error),
        })

    code = request.GET.get('code')
    state = request.GET.get('state')
    expected_state = request.session.pop('google_oauth_state', None)

    if not code:
        if not state:
            return redirect('login')
        return render(request, 'publisher/login.html', {'error': 'Falta el código de autorización'})
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return render(request, 'publisher/login.html', {'error': 'Estado OAuth inválido'})

    client_id, client_secret = settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    redirect_uri = _google_redirect_uri(request)

    try:
        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=30,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get('access_token')
        if not access_token:
            raise ValueError(f"Google no retornó access_token: {token_data}")

        me_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30,
        )
        me_resp.raise_for_status()
        me = me_resp.json()
    except Exception as e:
        log.exception("Error en flujo OAuth de Google")
        return render(request, 'publisher/login.html', {'error': f'Error autenticando con Google: {e}'})

    google_id = str(me.get('id', ''))
    if not google_id:
        return render(request, 'publisher/login.html', {'error': 'Google no retornó un id de usuario'})

    email = (me.get('email') or '').strip().lower()
    name = me.get('name') or google_id

    # 🔒 Validación de Whitelist de Correos
    if not _is_email_authorized(email):
        log.warning(f"Intento de acceso rechazado por whitelist para el correo: {email}")
        return render(request, 'publisher/login.html', {
            'error': f'Acceso denegado: El correo ({email}) no está en la lista de usuarios autorizados. Contacta al administrador.'
        })

    user, created = User.objects.get_or_create(
        username=f"google_{google_id}",
        defaults={
            'email': email or f"google_{google_id}@google.local",
            'first_name': name,
        },
    )
    if not user.is_active:
        user.is_active = True
        user.save()

    login(request, user)

    if created:
        _seed_user_config(user)
        log.info(f"Nuevo usuario registrado: {user.username} ({email})")

    return redirect('dashboard')


def _is_email_authorized(email: str) -> bool:
    """Verifica si un correo está autorizado mediante variable de entorno o base de datos."""
    if not email:
        return False
    
    email_clean = email.strip().lower()
    
    # 1. Verificar lista en variable de entorno ALLOWED_EMAILS
    allowed_env = getattr(settings, 'ALLOWED_EMAILS', [])
    for allowed in allowed_env:
        allowed = allowed.strip().lower()
        if not allowed:
            continue
        if allowed.startswith('@') and email_clean.endswith(allowed):
            return True
        if email_clean == allowed:
            return True

    # 2. Verificar tabla AllowedEmail en base de datos
    from .models import AllowedEmail
    try:
        has_any_db_rule = AllowedEmail.objects.filter(is_active=True).exists()
        # Si no hay reglas ni en ENV ni en BD, permitir el primer acceso y registrarlo
        if not allowed_env and not has_any_db_rule:
            AllowedEmail.objects.get_or_create(email=email_clean, defaults={'is_active': True})
            return True

        return AllowedEmail.objects.filter(email__iexact=email_clean, is_active=True).exists()
    except Exception as e:
        log.exception(f"Error verificando whitelist en BD: {e}")
        # Si hay error con la BD pero no hay env vars, por seguridad permitir si env está vacío
        return len(allowed_env) == 0


def logout_view(request):
    logout(request)
    return redirect('login')
