COUNTRY_NAMES = {
    'CO': 'Colombia', 'MX': 'México', 'PE': 'Perú',
    'AR': 'Argentina', 'CL': 'Chile', 'EC': 'Ecuador',
    'BO': 'Bolivia', 'VE': 'Venezuela', 'CR': 'Costa Rica',
    'PA': 'Panamá', 'BR': 'Brasil', 'CU': 'Cuba',
    'DO': 'República Dominicana', 'GT': 'Guatemala',
    'SV': 'El Salvador', 'HN': 'Honduras', 'NI': 'Nicaragua',
    'PY': 'Paraguay', 'UY': 'Uruguay',
}

COUNTRY_FLAGS = {
    'CO': '🇨🇴', 'MX': '🇲🇽', 'PE': '🇵🇪',
    'AR': '🇦🇷', 'CL': '🇨🇱', 'EC': '🇪🇨',
    'BO': '🇧🇴', 'VE': '🇻🇪', 'CR': '🇨🇷',
    'PA': '🇵🇦', 'BR': '🇧🇷', 'CU': '🇨🇺',
    'DO': '🇩🇴', 'GT': 'Guatemala', 'SV': 'El Salvador',
    'HN': '🇭🇳', 'NI': '🇳🇮', 'PY': '🇵🇾',
    'UY': '🇺🇾',
}


def _get_config(user, key, default=""):
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(key, default)
    try:
        from .models import UserConfig
        return UserConfig.objects.get(user=user, key=key).value
    except Exception:
        return default


_CONTEST_END_HOUR = 18
_CONTEST_END_MINUTE = 5
_COL_OFFSET = -5  # UTC-5


def _contest_finished() -> bool:
    from datetime import datetime, timezone, timedelta
    now_col = datetime.now(timezone(timedelta(hours=_COL_OFFSET)))
    end = now_col.replace(hour=_CONTEST_END_HOUR, minute=_CONTEST_END_MINUTE, second=0, microsecond=0)
    return now_col >= end


def build_description(user, competition_data: dict, final: bool = False, scope: str = 'LATAM', top_n: int = 10) -> str:
    """Genera la descripción de publicación para un ranking (LATAM o país específico)."""
    saved_text = _get_config(user, "publication_text", "").strip()
    if saved_text and scope == 'LATAM':
        return saved_text

    competition_name = _get_config(user, "competition_name", "Competencia RPC 2026")
    total_submissions = competition_data.get("total_submissions", 0)
    teams_with_solved = competition_data.get("teams_with_solved", 0)
    total_teams = competition_data.get("total_teams", 0)
    activated_by = _get_config(user, "activated_by", "")

    # Ámbito / País
    is_latam = (scope.upper() in ('LATAM', 'GLOBAL', 'ALL', ''))
    if is_latam:
        scope_title = f"Top {top_n} Latinoamérica"
        scope_hashtag = "#Latinoamerica"
    else:
        c_code = scope.upper()
        c_name = COUNTRY_NAMES.get(c_code, scope)
        flag = COUNTRY_FLAGS.get(c_code, "")
        scope_title = f"Top {top_n} {c_name} {flag}".strip()
        scope_hashtag = f"#{c_name.replace(' ', '')}"

    if final or _contest_finished():
        intro = f"🏆 ¡Tabla FINAL - {scope_title} de la {competition_name}!"
    else:
        intro = f"📊 Así va el {scope_title} de la {competition_name}:"

    footer = "(Automatizado por RPC Social Stream"
    if activated_by:
        footer += f", gracias {activated_by} por activarme :)"
    footer += ")"

    stats_line = ""
    if total_submissions > 0:
        stats_line = f"\n\n📈 En la maratón se han registrado {total_submissions} envíos totales, con {teams_with_solved} de {total_teams} equipos sumando problemas resueltos."

    return (
        f"{intro}"
        f"{stats_line}\n\n"
        f"¡Mucho éxito a todos los equipos competidores! 🚀💻\n"
        f"#RPC #RedProgramacionCompetitiva #ProgramacionCompetitiva {scope_hashtag} #TodosSomosRPC #CreciendoTodosJuntos\n\n"
        f"{footer}"
    )


def build_first_solution_description(user, fs_data: dict) -> str:
    """Genera el texto de celebración para un evento First Solution."""
    competition_name = _get_config(user, "competition_name", "Competencia RPC 2026")
    activated_by = _get_config(user, "activated_by", "")

    letter = fs_data.get("problem_letter", "A").upper()
    prob_name = fs_data.get("problem_name", letter)
    team_name = fs_data.get("team_name", "Equipo")
    university = fs_data.get("university", "")
    country_code = fs_data.get("country_code", "CO").upper()
    country_name = fs_data.get("country_name") or COUNTRY_NAMES.get(country_code, "Latinoamérica")
    flag = COUNTRY_FLAGS.get(country_code, "")
    time_min = fs_data.get("time_minutes", 0)
    lang = fs_data.get("language", "C++")

    univ_str = f" de {university}" if university and university != "Desconocida" else ""
    country_str = f" {flag} ({country_name})" if country_name else ""

    contest_tag = "#" + "".join(e for e in competition_name if e.isalnum())

    footer = "(Automatizado por RPC Social Stream"
    if activated_by:
        footer += f", gracias {activated_by} por activarme :)"
    footer += ")"

    return (
        f"🎈 ¡FIRST SOLUTION - PROBLEMA {letter}! 🎈\n\n"
        f"El equipo \"{team_name}\"{univ_str}{country_str} ha sido el PRIMERO en resolver el Problema {letter} ({prob_name}) "
        f"en el minuto {time_min} de la maratón utilizando {lang}! ⚡\n\n"
        f"¡Enhorabuenas y felicitaciones por esta gran hazaña! 👏🏆\n\n"
        f"#RPC #RedProgramacionCompetitiva #FirstSolution #Problema{letter} {contest_tag} #ProgramacionCompetitiva\n\n"
        f"{footer}"
    )
