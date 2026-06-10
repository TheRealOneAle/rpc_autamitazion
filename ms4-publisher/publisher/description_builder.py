def _get_config(key, default=""):
    from .models import SystemConfig
    try:
        return SystemConfig.objects.get(key=key).value
    except SystemConfig.DoesNotExist:
        return default


_CONTEST_END_HOUR   = 18
_CONTEST_END_MINUTE = 5
_COL_OFFSET = -5  # UTC-5


def _contest_finished() -> bool:
    return False  # deshabilitado temporalmente para pruebas
    from datetime import datetime, timezone, timedelta
    now_col = datetime.now(timezone(timedelta(hours=_COL_OFFSET)))
    end = now_col.replace(hour=_CONTEST_END_HOUR, minute=_CONTEST_END_MINUTE, second=0, microsecond=0)
    return now_col >= end


def build_description(competition_data: dict) -> str:
    competition_name  = _get_config("competition_name", "Competencia RPC 2026")
    total_submissions = competition_data.get("total_submissions", 0)
    teams_with_solved = competition_data.get("teams_with_solved", 0)
    total_teams       = competition_data.get("total_teams", 0)
    activated_by      = _get_config("activated_by", "")

    if _contest_finished():
        intro = f"Asi quedo la parte alta del tablero FINAL de la {competition_name}."
    else:
        intro = f"Asi va el tablero hasta ahora de la {competition_name}."

    footer = "(Automatizado por rpc social stream"
    if activated_by:
        footer += f", gracias {activated_by} por activarme :)"
    footer += ")"

    return (
        f"{intro} "
        f"Se realizaron en total {total_submissions} envios, donde {teams_with_solved} equipos "
        f"(de {total_teams} en competencia) "
        f"#TodosSomosRPC #CreciendoTodosJuntos\n\n"
        f"{footer}"
    )
