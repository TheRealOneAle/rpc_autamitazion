def _get_config(key, default=""):
    from .models import SystemConfig
    try:
        return SystemConfig.objects.get(key=key).value
    except SystemConfig.DoesNotExist:
        return default


def build_description(competition_data: dict) -> str:
    """Construye el texto de la publicación a partir de los datos del ranking."""
    competition_name = _get_config("competition_name", "Competencia RPC 2026")
    landing_url = _get_config("landing_page_url", "https://rpc.ufps.edu.co")

    teams = competition_data.get("teams", [])
    total_teams = len(teams)
    total_submissions = sum(int(t.get("submissions", t.get("points", 0)) or 0) for t in teams)

    top3 = teams[:3]
    top3_lines = []
    for i, team in enumerate(top3, start=1):
        name = team.get("userfullname") or team.get("name", f"Equipo {i}")
        solved = team.get("problemas_resueltos") or team.get("solved", 0)
        top3_lines.append(f"  {i}. {name} — {solved} problema(s) resuelto(s)")

    top3_text = "\n".join(top3_lines) if top3_lines else "  (sin datos)"

    lines = [
        f"🏆 {competition_name}",
        "",
        f"📊 {total_teams} equipos participantes | {total_submissions} envíos totales",
        "",
        "🥇 Top 3:",
        top3_text,
        "",
        f"🔗 Más información: {landing_url}",
        "",
        "#TodosSomosRPC #CreciendoTodosJuntos",
    ]
    return "\n".join(lines)
