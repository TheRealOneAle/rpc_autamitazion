import logging
import time
import requests
from django.conf import settings

log = logging.getLogger(__name__)

MAX_RETRIES = 3


def _get_config(key, default=""):
    from .models import SystemConfig
    try:
        return SystemConfig.objects.get(key=key).value
    except SystemConfig.DoesNotExist:
        return default


def _get_user_config(user, key, default=""):
    from .models import UserConfig
    try:
        return UserConfig.objects.get(user=user, key=key).value
    except UserConfig.DoesNotExist:
        return default


def _fetch_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """Llama a un endpoint con reintentos exponenciales."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = getattr(requests, method)(url, timeout=120, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            log.warning(f"Intento {attempt}/{MAX_RETRIES} fallido para {url}: {e}. Reintentando en {wait}s...")
            time.sleep(wait)


def _user_contest_params(user):
    """Devuelve (year, contest) del usuario. Si faltan, lanza ValueError."""
    year = _get_user_config(user, "boca_year", "").strip()
    contest = _get_user_config(user, "boca_contest", "").strip()
    if not year or not contest:
        raise ValueError("El usuario no tiene configurado año/contest de Boca")
    return year, str(int(contest)).zfill(2)


def _bd_url(base, path, year, contest):
    url = f"{base}{path}"
    if year and contest:
        url += f"?contest={year}%2F{str(int(contest)).zfill(2)}"
    return url


def _publish_for_user(user, final=False, force=False):
    """Ciclo completo para un usuario: leer datos de su contest → generar imagen → publicar en FB."""
    from .models import PublicationLog
    from .facebook_publisher import publish_photo
    from .description_builder import build_description

    user_label = getattr(user, "username", "?")
    log.info(f"[ORQ] Iniciando ciclo para {user_label} (final={final}, force={force})")
    print(f"[ORQ] Iniciando ciclo para {user_label} (final={final}, force={force})")

    # Botón "detener publicaciones" por usuario
    if not force:
        proceso_activo = _get_user_config(user, "proceso_activo", "false").lower()
        if proceso_activo != "true":
            log.info(f"[ORQ] {user_label}: proceso_activo=False. Ciclo omitido.")
            print(f"[ORQ] {user_label}: proceso_activo=False. Ciclo omitido.")
            return

    try:
        year, contest = _user_contest_params(user)
    except ValueError as e:
        log.warning(f"[ORQ] {user_label}: {e}")
        print(f"[ORQ] {user_label}: {e}")
        PublicationLog.objects.create(user=user, status="SKIPPED", error_message=str(e))
        return

    # Token/página propios del usuario
    from .models import SocialToken
    token_obj = SocialToken.objects.filter(user=user).order_by('-updated_at').first()
    if token_obj is None:
        log.warning(f"[ORQ] {user_label}: no tiene token de Facebook configurado.")
        print(f"[ORQ] {user_label}: no tiene token de Facebook.")
        PublicationLog.objects.create(user=user, status="SKIPPED", error_message="Sin token de Facebook")
        return

    ms1_url = _get_config("ms1_url") or settings.MS1_URL
    ms2_url = _get_config("ms2_url") or settings.MS2_URL

    competition_data = None
    try:
        print(f"[ORQ] {user_label}: Obteniendo ranking de {ms1_url}...")
        r1 = _fetch_with_retry("get", _bd_url(ms1_url, "/api/ranking", year, contest))
        raw = r1.json()
        r_stats = _fetch_with_retry("get", _bd_url(ms1_url, "/api/stats", year, contest))
        stats = r_stats.json()
        competition_data = {
            "teams": raw.get("rows", raw.get("teams", [])),
            "total_teams":       stats.get("total_teams", 0),
            "total_submissions": stats.get("total_submissions", 0),
            "teams_with_solved": stats.get("teams_with_solved", 0),
        }

        print(f"[ORQ] {user_label}: Generando imagen...")
        _fetch_with_retry("post", _bd_url(ms2_url, "/generate", year, contest))
        r2 = _fetch_with_retry("get", _bd_url(ms2_url, "/ranking.jpg", year, contest))
        image_bytes = r2.content

        description = build_description(user, competition_data, final=final)
        print(f"[ORQ] {user_label}: Publicando en Facebook...")
        post_id = publish_photo(
            image_bytes, description,
            access_token=token_obj.access_token,
            page_id=token_obj.page_id,
        )

        PublicationLog.objects.create(
            user=user,
            status="SUCCESS",
            post_id=post_id,
            competition_data=competition_data,
        )
        log.info(f"[ORQ] {user_label}: ciclo completado. post_id={post_id}")
        print(f"[ORQ] {user_label}: ciclo completado. post_id={post_id}")

    except Exception as e:
        log.exception(f"[ORQ] {user_label}: error en ciclo: {e}")
        print(f"[ORQ] {user_label}: ERROR en ciclo: {e}")
        PublicationLog.objects.create(
            user=user,
            status="ERROR",
            error_message=str(e),
            competition_data=competition_data,
        )


def orchestrate_all(final=False):
    """Recorre todos los usuarios activos y publica para cada uno."""
    from django.contrib.auth.models import User
    print(f"[ORQ] orchestrate_all(final={final}) — usuarios activos: {User.objects.filter(is_active=True).count()}")
    for user in User.objects.filter(is_active=True):
        try:
            _publish_for_user(user, final=final)
        except Exception as e:
            log.exception(f"[ORQ] Error global para {user.username}: {e}")
            print(f"[ORQ] Error global para {user.username}: {e}")


def orchestrate_publication(force=False, final=False):
    """Compat: publica solo para el primer usuario activo (legado)."""
    from django.contrib.auth.models import User
    user = User.objects.filter(is_active=True).first()
    if user is None:
        log.info("No hay usuarios activos; ciclo omitido.")
        return
    _publish_for_user(user, final=final, force=force)
