def _get_config(key, default=""):
    from .models import SystemConfig
    try:
        return SystemConfig.objects.get(key=key).value
    except SystemConfig.DoesNotExist:
        return default


def build_description(competition_data: dict) -> str:
    competition_name  = _get_config("competition_name", "Competencia RPC 2026")
    total_submissions = competition_data.get("total_submissions", 0)
    teams_with_solved = competition_data.get("teams_with_solved", 0)
    total_teams       = competition_data.get("total_teams", 0)

    return (
        f"Asi quedo la parte alta del tablero FINAL de la {competition_name}. "
        f"Se realizaron en total {total_submissions} envios, donde {teams_with_solved} equipos "
        f"(de {total_teams} en competencia) "
        f"#TodosSomosRPC #CreciendoTodosJuntos"
    )
