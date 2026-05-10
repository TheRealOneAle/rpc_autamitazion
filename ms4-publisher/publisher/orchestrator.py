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


def _fetch_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """Llama a un endpoint con reintentos exponenciales."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = getattr(requests, method)(url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            log.warning(f"Intento {attempt}/{MAX_RETRIES} fallido para {url}: {e}. Reintentando en {wait}s...")
            time.sleep(wait)


def orchestrate_publication():
    """Ciclo completo: leer datos → generar imagen → publicar en FB → loguear → notificar."""
    from .models import PublicationLog
    from .facebook_publisher import publish_photo
    from .description_builder import build_description
    from .messaging import publish_ranking_event

    log.info("Iniciando ciclo de publicación...")

    proceso_activo = _get_config("proceso_activo", "false").lower()
    if proceso_activo != "true":
        log.info("proceso_activo=False. Ciclo omitido.")
        PublicationLog.objects.create(status="SKIPPED")
        return

    ms1_url = _get_config("ms1_url") or settings.MS1_URL
    ms2_url = _get_config("ms2_url") or settings.MS2_URL

    competition_data = None
    try:
        r1 = _fetch_with_retry("get", f"{ms1_url}/api/ranking")
        raw = r1.json()
        r_stats = _fetch_with_retry("get", f"{ms1_url}/api/stats")
        stats = r_stats.json()
        competition_data = {
            "teams": raw.get("rows", raw.get("teams", [])),
            "total_teams":       stats.get("total_teams", 0),
            "total_submissions": stats.get("total_submissions", 0),
            "teams_with_solved": stats.get("teams_with_solved", 0),
        }

        _fetch_with_retry("post", f"{ms2_url}/generate")
        r2 = _fetch_with_retry("get", f"{ms2_url}/ranking.jpg")
        image_bytes = r2.content

        description = build_description(competition_data)
        post_id = publish_photo(image_bytes, description)

        PublicationLog.objects.create(
            status="SUCCESS",
            post_id=post_id,
            competition_data=competition_data,
        )
        log.info(f"Ciclo completado. post_id={post_id}")

        publish_ranking_event(competition_data, post_id)

    except Exception as e:
        log.exception(f"Error en ciclo de publicación: {e}")
        PublicationLog.objects.create(
            status="ERROR",
            error_message=str(e),
            competition_data=competition_data,
        )
