import json
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


def _bd_url(base, path, year, contest, country=None, top_n=None):
    url = f"{base}{path}"
    params = []
    if year and contest:
        params.append(f"contest={year}%2F{str(int(contest)).zfill(2)}")
    if country and country.upper() not in ('LATAM', 'GLOBAL', 'ALL'):
        params.append(f"country={country}")
    if top_n:
        params.append(f"top_n={top_n}")

    if params:
        url += ("&" if "?" in url else "?") + "&".join(params)
    return url


def _publish_for_user(user, final=False, force=False):
    """Ciclo completo para un usuario: itera sobre todos sus rankings activos (LATAM y países) y publica consecutivamente."""
    from .models import PublicationLog, SocialToken
    from .facebook_publisher import publish_photo
    from .description_builder import build_description

    user_label = getattr(user, "username", "?")
    log.info(f"[ORQ] Iniciando ciclo para {user_label} (final={final}, force={force})")
    print(f"[ORQ] Iniciando ciclo para {user_label} (final={final}, force={force})")

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

    token_obj = SocialToken.objects.filter(user=user).order_by('-updated_at').first()
    if token_obj is None:
        log.warning(f"[ORQ] {user_label}: no tiene token de Facebook configurado.")
        print(f"[ORQ] {user_label}: no tiene token de Facebook.")
        PublicationLog.objects.create(user=user, status="SKIPPED", error_message="Sin token de Facebook")
        return

    ms1_url = _get_config("ms1_url") or settings.MS1_URL
    ms2_url = _get_config("ms2_url") or settings.MS2_URL

    # Obtener configuración de Top N y rankings activos
    top_n_raw = _get_user_config(user, "top_n_size", "10").strip()
    top_n = int(top_n_raw) if top_n_raw.isdigit() else 10

    active_rankings_json = _get_user_config(user, "active_rankings", '["LATAM"]').strip()
    try:
        active_rankings = json.loads(active_rankings_json)
        if not isinstance(active_rankings, list) or not active_rankings:
            active_rankings = ["LATAM"]
    except Exception:
        active_rankings = ["LATAM"]

    print(f"[ORQ] {user_label}: Rankings a publicar: {active_rankings} con Top {top_n}")

    # Obtener estadísticas generales
    competition_data = None
    try:
        r_stats = _fetch_with_retry("get", _bd_url(ms1_url, "/api/stats", year, contest))
        stats = r_stats.json()
        competition_data = {
            "total_teams":       stats.get("total_teams", 0),
            "total_submissions": stats.get("total_submissions", 0),
            "teams_with_solved": stats.get("teams_with_solved", 0),
        }
    except Exception as e:
        log.warning(f"[ORQ] {user_label}: no se pudieron obtener stats generales: {e}")
        competition_data = {"total_teams": 0, "total_submissions": 0, "teams_with_solved": 0}

    # Publicar secuencialmente cada ranking seleccionado
    for idx, scope in enumerate(active_rankings):
        try:
            print(f"[ORQ] {user_label}: [{idx+1}/{len(active_rankings)}] Procesando ranking '{scope}'...")

            # 1. Obtener ranking específico
            r_rank = _fetch_with_retry("get", _bd_url(ms1_url, "/api/ranking", year, contest, country=scope, top_n=top_n))
            rank_data = r_rank.json()
            teams_scope = rank_data.get("rows", [])

            if not teams_scope:
                print(f"[ORQ] {user_label}: Sin equipos para ranking '{scope}'. Omitiendo...")
                continue

            scope_competition_data = {
                **competition_data,
                "teams": teams_scope,
            }

            # 2. Generar imagen
            _fetch_with_retry("post", _bd_url(ms2_url, "/generate", year, contest, country=scope, top_n=top_n))
            r_img = _fetch_with_retry("get", _bd_url(ms2_url, "/ranking.jpg", year, contest, country=scope, top_n=top_n))
            image_bytes = r_img.content

            # 3. Construir descripción
            description = build_description(user, scope_competition_data, final=final, scope=scope, top_n=top_n)

            # 4. Publicar en Facebook
            print(f"[ORQ] {user_label}: Publicando '{scope}' en Facebook...")
            post_id = publish_photo(
                image_bytes, description,
                access_token=token_obj.access_token,
                page_id=token_obj.page_id,
            )

            PublicationLog.objects.create(
                user=user,
                status="SUCCESS",
                post_id=post_id,
                competition_data={
                    "scope": scope,
                    "top_n": top_n,
                    **scope_competition_data,
                },
            )
            log.info(f"[ORQ] {user_label}: '{scope}' publicado exitosamente. post_id={post_id}")
            print(f"[ORQ] {user_label}: '{scope}' publicado. post_id={post_id}")

            # Retardo de 3.5 segundos entre publicaciones para cumplir políticas de Meta
            if idx < len(active_rankings) - 1:
                time.sleep(3.5)

        except Exception as e:
            log.exception(f"[ORQ] {user_label}: error publicando '{scope}': {e}")
            print(f"[ORQ] {user_label}: ERROR publicando '{scope}': {e}")
            PublicationLog.objects.create(
                user=user,
                status="ERROR",
                error_message=f"[{scope}] {e}",
                competition_data=competition_data,
            )


def publish_first_solution_event(fs_data: dict, user=None):
    """Publica inmediatamente un evento First Solution en Facebook y lo registra en BD."""
    from django.contrib.auth.models import User
    from .models import FirstSolutionEvent, SocialToken
    from .facebook_publisher import publish_photo
    from .description_builder import build_first_solution_description

    target_user = user or User.objects.filter(is_active=True).first()
    if target_user is None:
        log.warning("[FS] No hay usuario activo para publicar First Solution.")
        return False, "No hay usuario activo"

    token_obj = SocialToken.objects.filter(user=target_user).order_by('-updated_at').first()
    if token_obj is None:
        log.warning("[FS] Usuario no tiene token de Facebook configurado.")
        return False, "Sin token de Facebook"

    year, contest = _user_contest_params(target_user)
    contest_key = f"{year}/{contest}"
    letter = fs_data.get("problem_letter", "A").upper()

    # Verificar si ya está registrado
    existing = FirstSolutionEvent.objects.filter(contest_key=contest_key, problem_letter=letter).first()
    if existing and existing.success and existing.post_id:
        log.info(f"[FS] First Solution para problema {letter} ya fue publicado previamente (post_id={existing.post_id}).")
        return True, f"Ya publicado (post_id={existing.post_id})"

    ms3_url = _get_config("ms3_url") or settings.MS3_URL

    # 1. Obtener imagen de tarjeta First Solution
    image_bytes = None
    try:
        card_url = f"{ms3_url}/card/first-solution"
        r_card = requests.post(card_url, json=fs_data, timeout=15)
        if r_card.status_code == 200:
            image_bytes = r_card.content
    except Exception as e:
        log.warning(f"[FS] No se pudo generar micro-tarjeta de {ms3_url}: {e}")

    # Fallback a globo simple si falló la tarjeta
    if not image_bytes:
        try:
            globo_url = f"{ms3_url}/globo/{letter}.png?contest={year}%2F{contest}"
            r_globo = requests.get(globo_url, timeout=15)
            if r_globo.status_code == 200:
                image_bytes = r_globo.content
        except Exception:
            pass

    # 2. Construir copy
    description = build_first_solution_description(target_user, fs_data)

    # 3. Publicar en Facebook
    try:
        if image_bytes:
            post_id = publish_photo(
                image_bytes, description,
                access_token=token_obj.access_token,
                page_id=token_obj.page_id,
            )
        else:
            from .facebook_publisher import publish_text
            post_id = publish_text(
                description,
                access_token=token_obj.access_token,
                page_id=token_obj.page_id,
            )

        # 4. Guardar evento
        FirstSolutionEvent.objects.update_or_create(
            contest_key=contest_key,
            problem_letter=letter,
            defaults={
                "user": target_user,
                "problem_name": fs_data.get("problem_name", letter),
                "problem_color": fs_data.get("problem_color", "#CF1F4A"),
                "team_name": fs_data.get("team_name", ""),
                "university": fs_data.get("university", ""),
                "university_acronym": fs_data.get("university_acronym", ""),
                "country_code": fs_data.get("country_code", "CO"),
                "country_name": fs_data.get("country_name", ""),
                "time_minutes": fs_data.get("time_minutes", 0),
                "language": fs_data.get("language", ""),
                "post_id": post_id,
                "success": True,
                "error_message": None,
            }
        )
        print(f"[FS] ¡First Solution Problema {letter} publicado exitosamente! post_id={post_id}")
        return True, post_id

    except Exception as e:
        log.exception(f"[FS] Error publicando First Solution {letter}: {e}")
        FirstSolutionEvent.objects.update_or_create(
            contest_key=contest_key,
            problem_letter=letter,
            defaults={
                "user": target_user,
                "problem_name": fs_data.get("problem_name", letter),
                "team_name": fs_data.get("team_name", ""),
                "university": fs_data.get("university", ""),
                "country_code": fs_data.get("country_code", "CO"),
                "time_minutes": fs_data.get("time_minutes", 0),
                "language": fs_data.get("language", ""),
                "success": False,
                "error_message": str(e),
            }
        )
        return False, str(e)


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
    """Compat: publica para el primer usuario activo."""
    from django.contrib.auth.models import User
    user = User.objects.filter(is_active=True).first()
    if user is None:
        log.info("No hay usuarios activos; ciclo omitido.")
        return
    _publish_for_user(user, final=final, force=force)
