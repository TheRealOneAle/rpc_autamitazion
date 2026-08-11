import hashlib
import os
import re
import threading
import time

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

app = Flask(__name__)

_BASE_DEFAULT = os.environ.get("BOCA_URL", "https://redprogramacioncompetitiva.com/contests/2026/06")
BOCA_USER = os.environ.get("BOCA_USER", "silux")
BOCA_PASS = os.environ.get("BOCA_PASS", "ovallos.")
CACHE_TTL = int(os.environ.get("CACHE_TTL", "60"))

# URL mutable en tiempo de ejecución (cambia con POST /config)
_config = {"base": _BASE_DEFAULT}

# Colores ICPC estándar por defecto cuando Boca no los expone en el HTML
DEFAULT_COLORS = [
    "#FF0000", "#0000FF", "#00CC00", "#FFFF00", "#FF8000",
    "#FF00FF", "#00FFFF", "#800080", "#804000", "#008000",
    "#000080", "#808000", "#008080", "#800000",
]

_cache = {"teams": None, "colors": None, "ts": 0}
_lock = threading.Lock()


def _hash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _login_and_fetch():
    base = _config["base"]
    session = requests.Session()
    session.get(f"{base}/index.php", timeout=15)
    sid = session.cookies.get("PHPSESSID", "")
    session.get(
        f"{base}/index.php",
        params={"name": BOCA_USER, "password": _hash(_hash(BOCA_PASS) + sid)},
        timeout=15,
    )
    resp = session.get(f"{base}/admin/score.php", timeout=15)
    resp.raise_for_status()
    return resp.text


def _extract_color(cell):
    color = cell.get("bgcolor") or ""
    if not color:
        m = re.search(
            r"background(?:-color)?:\s*(#[0-9a-fA-F]{3,6})", cell.get("style", "")
        )
        color = m.group(1) if m else ""
    return color or None


def _is_solved(cell_text):
    # Boca usa formato "intentos/minutos" (ej: "1/84"). No resuelto: "", "-", "N/-"
    if not cell_text or cell_text == "-":
        return False
    return bool(re.match(r"^\d+/\d+$", cell_text))


def _parse_total(text):
    m = re.match(r"(\d+)(?:/\d+)?\s*\((\d+)\)", text or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r"^(\d+)$", (text or "").strip())
    if m2:
        return int(m2.group(1)), 0
    return None, None


def _parse(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 3:
        raise ValueError(f"Se esperaban al menos 3 tablas, se encontraron {len(tables)}")

    table = tables[2]
    rows = table.find_all("tr")

    problem_colors = []
    problem_col_start = 2  # índice donde comienza la primera columna de problema
    teams = []
    seen_names = set()  # deduplicar: Boca repite cada fila en el HTML
    header_found = False

    for row in rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(strip=True) for c in cells]
        if not texts:
            continue

        if texts[0] == "#" and not header_found:
            header_found = True
            for col_idx, cell in enumerate(cells):
                t = cell.get_text(strip=True)
                if len(t) == 1 and t.isupper():
                    if not problem_colors:
                        problem_col_start = col_idx  # primer problema en esta columna
                    idx = len(problem_colors)
                    color = _extract_color(cell) or DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]
                    problem_colors.append(color)
            continue

        if not header_found:
            continue

        try:
            pos = int(texts[0])
        except (ValueError, IndexError):
            continue

        name = texts[1] if len(texts) > 1 else ""
        if name in seen_names:
            continue
        seen_names.add(name)

        flag_img = cells[1].find("img") if len(cells) > 1 else None
        country = flag_img.get("alt", "").strip() if flag_img else ""

        n = len(problem_colors)
        solved_problems = []

        for i in range(n):
            cidx = problem_col_start + i
            if cidx < len(texts) and _is_solved(texts[cidx]):
                solved_problems.append(i + 1)  # 1-indexed

        n_solved, penalty = _parse_total(texts[-1] if texts else "")
        if n_solved is None:
            n_solved = len(solved_problems)
            penalty = 0

        teams.append({
            "pos": len(teams) + 1,  # posición 1-indexed en orden de aparición
            "usernumber": pos,
            "userfullname": name,
            "country": country or None,
            "problemas_resueltos": n_solved,
            "points": penalty,
            "solved_problems": solved_problems,
        })

    color_list = [(i + 1, c) for i, c in enumerate(problem_colors)]
    return teams, color_list


def _get_data():
    now = time.time()
    with _lock:
        cached_teams = _cache["teams"]
        cached_colors = _cache["colors"]
        cached_ts = _cache["ts"]

    if cached_teams is not None and now - cached_ts <= CACHE_TTL:
        return cached_teams, cached_colors

    try:
        html = _login_and_fetch()
        teams, color_list = _parse(html)
        with _lock:
            _cache["teams"] = teams
            _cache["colors"] = color_list
            _cache["ts"] = time.time()
        return teams, color_list
    except Exception as e:
        print(f"[scraper] error al obtener datos de Boca: {e}", flush=True)
        if cached_teams is None:
            raise
        print("[scraper] usando datos en caché (posiblemente desactualizados)", flush=True)
        return cached_teams, cached_colors


@app.route("/api/teams", methods=["GET"])
def get_teams():
    try:
        teams, _ = _get_data()
        rows = [
            {"usernumber": t["usernumber"], "userfullname": t["userfullname"], "country": t["country"]}
            for t in teams
        ]
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/problems", methods=["GET"])
def get_problems():
    try:
        _, colors = _get_data()
        rows = [{"problemnumber": n, "problemcolor": c} for n, c in colors]
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/problems/count", methods=["GET"])
def get_problems_count():
    try:
        _, colors = _get_data()
        return jsonify({"success": True, "count": len(colors)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/teams/ac", methods=["GET"])
def get_teams_ac():
    try:
        teams, _ = _get_data()
        rows = [
            {"usernumber": t["usernumber"], "runproblem": prob}
            for t in teams
            for prob in t["solved_problems"]
        ]
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ranking", methods=["GET"])
def get_ranking():
    try:
        teams, colors = _get_data()
        rows = [
            {
                "pos": t["pos"],
                "userfullname": t["userfullname"],
                "country": t["country"],
                "usernumber": t["usernumber"],
                "problemas_resueltos": t["problemas_resueltos"],
                "points": t["points"],
            }
            for t in teams[:10]
        ]
        return jsonify({"success": True, "rows": rows, "cantidadProblemas": len(colors)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ranking/full", methods=["GET"])
def get_ranking_full():
    try:
        teams, _ = _get_data()
        rows = [
            {
                "pos": t["pos"],
                "userfullname": t["userfullname"],
                "country": t["country"],
                "usernumber": t["usernumber"],
                "problemas_resueltos": t["problemas_resueltos"],
                "points": t["points"],
            }
            for t in teams
        ]
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    try:
        teams, _ = _get_data()
        total_teams = len(teams)
        teams_with_solved = sum(1 for t in teams if t["problemas_resueltos"] > 0)
        total_submissions = sum(len(t["solved_problems"]) for t in teams)
        return jsonify({
            "success": True,
            "total_teams": total_teams,
            "total_submissions": total_submissions,
            "teams_with_solved": teams_with_solved,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/config", methods=["GET"])
def get_config():
    base = _config["base"]
    parts = base.rstrip("/").split("/")
    contest_raw = parts[-1]
    year = parts[-2]
    return jsonify({"url": base, "year": year, "contest": str(int(contest_raw))})


@app.route("/config", methods=["POST"])
def set_config():
    data = request.get_json() or {}
    year = str(data.get("year", "")).strip()
    contest = str(data.get("contest", "")).strip()
    if not year or not contest:
        return jsonify({"error": "year y contest son requeridos"}), 400

    base_root = _BASE_DEFAULT.split("/contests/")[0]
    contest_padded = str(int(contest)).zfill(2)
    new_base = f"{base_root}/contests/{year}/{contest_padded}"
    _config["base"] = new_base

    with _lock:
        _cache["teams"] = None
        _cache["colors"] = None
        _cache["ts"] = 0

    print(f"[config] URL actualizada a {new_base}", flush=True)
    return jsonify({"url": new_base, "year": year, "contest": contest})


def _warmup():
    """Precalienta el caché al arrancar para que el primer request no espere."""
    import time as _t
    _t.sleep(2)  # espera mínima a que Flask esté listo
    try:
        print("[warmup] precalentando caché...", flush=True)
        _get_data()
        print("[warmup] caché listo", flush=True)
    except Exception as e:
        print(f"[warmup] falló (se reintentará en el primer request): {e}", flush=True)


threading.Thread(target=_warmup, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3001)))
