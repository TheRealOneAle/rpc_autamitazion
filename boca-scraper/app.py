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

# Caché por contest: {contest_key: {"teams":..., "colors":..., "ts":...}}
_caches = {}
_lock = threading.Lock()


def _contest_key(base):
    parts = base.rstrip("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


def _parse_contest_params():
    """Extrae (year, contest) desde query params. Soporta contest=YYYY/NN o year+contest."""
    year = (request.args.get("year") or "").strip()
    contest = (request.args.get("contest") or "").strip()
    if "/" in contest:
        parts = contest.split("/")
        year = parts[0].strip()
        contest = parts[1].strip()
    return year, contest


def _contest_base(year, contest):
    if not year or not contest:
        return _config["base"]
    base_root = _BASE_DEFAULT.split("/contests/")[0]
    contest_padded = str(int(contest)).zfill(2)
    return f"{base_root}/contests/{year}/{contest_padded}"


def _base_from_request():
    year, contest = _parse_contest_params()
    if year and contest:
        return _contest_base(year, contest), f"{year}/{str(int(contest)).zfill(2)}"
    base = _config["base"]
    return base, _contest_key(base)


# Colores ICPC estándar por defecto cuando Boca no los expone en el HTML
DEFAULT_COLORS = [
    "#FF0000", "#0000FF", "#00CC00", "#FFFF00", "#FF8000",
    "#FF00FF", "#00FFFF", "#800080", "#804000", "#008000",
    "#000080", "#808000", "#008080", "#800000",
]

NAMED_COLORS = {
    "red": "#FF0000", "blue": "#0000FF", "green": "#008000", "yellow": "#FFFF00",
    "orange": "#FFA500", "purple": "#800080", "magenta": "#FF00FF", "cyan": "#00FFFF",
    "pink": "#FFC0CB", "black": "#000000", "white": "#FFFFFF", "gray": "#808080",
    "grey": "#808080", "salmon": "#FA8072", "gold": "#FFD700", "lime": "#00FF00",
    "navy": "#000080", "teal": "#008080", "brown": "#8B4513", "darkgreen": "#006400",
}


def _normalize_color(raw):
    """Normaliza un color a formato hexadecimal #RRGGBB."""
    if not raw:
        return None
    raw = str(raw).strip().lower()
    if raw in NAMED_COLORS:
        return NAMED_COLORS[raw]
    raw_clean = raw.lstrip("#")
    if re.match(r"^[0-9a-fA-F]{6}$", raw_clean):
        return f"#{raw_clean.upper()}"
    if re.match(r"^[0-9a-fA-F]{3}$", raw_clean):
        return f"#{raw_clean[0]*2}{raw_clean[1]*2}{raw_clean[2]*2}".upper()
    return None


def _hash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _fetch_problems_from_db():
    """Opción 1: Consulta directa a la base de datos PostgreSQL de BOCA (problemtable)."""
    db_host = os.environ.get("BOCA_DB_HOST")
    if not db_host:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=db_host,
            port=int(os.environ.get("BOCA_DB_PORT", "5432")),
            dbname=os.environ.get("BOCA_DB_NAME", "bkboca"),
            user=os.environ.get("BOCA_DB_USER", "postgres"),
            password=os.environ.get("BOCA_DB_PASS", "1234"),
            connect_timeout=5,
        )
        try:
            with conn.cursor() as cur:
                contest_num = os.environ.get("BOCA_CONTEST_NUMBER")
                if contest_num:
                    cur.execute(
                        "SELECT problemnumber, problemname, problemcolor, problemcolorname "
                        "FROM problemtable WHERE contestnumber = %s ORDER BY problemnumber ASC",
                        (contest_num,)
                    )
                else:
                    cur.execute(
                        "SELECT problemnumber, problemname, problemcolor, problemcolorname "
                        "FROM problemtable ORDER BY problemnumber ASC"
                    )
                rows = cur.fetchall()
                problems = []
                for r in rows:
                    p_num = int(r[0])
                    p_name = (r[1] or chr(64 + p_num)).strip()
                    p_color = _normalize_color(r[2]) or _normalize_color(r[3])
                    if not p_color:
                        p_color = DEFAULT_COLORS[(p_num - 1) % len(DEFAULT_COLORS)]
                    problems.append((p_num, p_name, p_color))
                print(f"[scraper] {len(problems)} problemas obtenidos desde BD BOCA", flush=True)
                return problems if problems else None
        finally:
            conn.close()
    except Exception as e:
        print(f"[scraper] advertencia: error al conectar con BD BOCA: {e}", flush=True)
        return None


def _fetch_problems_from_admin(base):
    """Opción 2: Scraping de la página de administración admin/problem.php de BOCA."""
    try:
        session = requests.Session()
        session.get(f"{base}/index.php", timeout=15)
        sid = session.cookies.get("PHPSESSID", "")
        session.get(
            f"{base}/index.php",
            params={"name": BOCA_USER, "password": _hash(_hash(BOCA_PASS) + sid)},
            timeout=15,
        )
        resp = session.get(f"{base}/admin/problem.php", timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 3:
            return None

        table = tables[2]
        rows = table.find_all("tr")
        problems = []
        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            p_num_text = cells[0].get_text(strip=True)
            if not p_num_text.isdigit():
                continue
            p_num = int(p_num_text)
            if p_num == 0:
                continue  # Problema general/fake 0
            p_name = cells[1].get_text(strip=True) if len(cells) > 1 else chr(64 + p_num)

            color_cell = cells[-1]
            color = None
            # 1. Input name="colorN"
            color_inp = color_cell.find("input", attrs={"name": re.compile(r"^color\d+$")})
            if color_inp and color_inp.get("value"):
                color = color_inp["value"].strip()
            # 2. Img title / alt
            if not color:
                img = color_cell.find("img")
                if img and img.get("title"):
                    color = img["title"].strip()
            # 3. Input name="colornameN"
            if not color:
                cname_inp = color_cell.find("input", attrs={"name": re.compile(r"^colorname\d+$")})
                if cname_inp and cname_inp.get("value") and cname_inp["value"] != "Can be empty":
                    color = cname_inp["value"].strip()

            norm_color = _normalize_color(color)
            if not norm_color:
                norm_color = DEFAULT_COLORS[(p_num - 1) % len(DEFAULT_COLORS)]

            problems.append((p_num, p_name, norm_color))

        print(f"[scraper] {len(problems)} problemas obtenidos desde admin/problem.php", flush=True)
        return problems if problems else None
    except Exception as e:
        print(f"[scraper] advertencia: error al scrapear admin/problem.php: {e}", flush=True)
        return None


def _login_and_fetch(base):
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
    return _normalize_color(color) or None


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
                    problem_colors.append((idx + 1, t, color))
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

    return teams, problem_colors


def _get_data(base):
    key = _contest_key(base)
    now = time.time()

    with _lock:
        cache = _caches.get(key)
        if cache is not None and now - cache["ts"] <= CACHE_TTL:
            return cache["teams"], cache["colors"]

    try:
        html = _login_and_fetch(base)
        teams, color_list = _parse(html)

        # Enriquecer colores usando BD BOCA (Opción 1) o admin/problem.php (Opción 2)
        admin_problems = _fetch_problems_from_db() or _fetch_problems_from_admin(base)
        if admin_problems:
            color_list = admin_problems

        with _lock:
            _caches[key] = {"teams": teams, "colors": color_list, "ts": time.time()}
        return teams, color_list
    except Exception as e:
        print(f"[scraper] error al obtener datos de {key}: {e}", flush=True)
        cache = _caches.get(key)
        if cache is None:
            raise
        print(f"[scraper] usando datos en caché de {key} (posiblemente desactualizados)", flush=True)
        return cache["teams"], cache["colors"]


@app.route("/api/teams", methods=["GET"])
def get_teams():
    try:
        base, _ = _base_from_request()
        teams, _ = _get_data(base)
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
        base, _ = _base_from_request()
        _, colors = _get_data(base)
        rows = [
            {
                "problemnumber": item[0],
                "problemname": item[1] if len(item) > 1 else chr(64 + item[0]),
                "problemcolor": item[2] if len(item) > 2 else item[1],
            }
            for item in colors
        ]
        return jsonify({"success": True, "rows": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/problems/count", methods=["GET"])
def get_problems_count():
    try:
        base, _ = _base_from_request()
        _, colors = _get_data(base)
        return jsonify({"success": True, "count": len(colors)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/teams/ac", methods=["GET"])
def get_teams_ac():
    try:
        base, _ = _base_from_request()
        teams, _ = _get_data(base)
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
        base, key = _base_from_request()
        teams, colors = _get_data(base)
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
        return jsonify({"success": True, "rows": rows, "cantidadProblemas": len(colors), "contest": key})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ranking/full", methods=["GET"])
def get_ranking_full():
    try:
        base, _ = _base_from_request()
        teams, _ = _get_data(base)
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
        base, _ = _base_from_request()
        teams, _ = _get_data(base)
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
        _caches.clear()

    print(f"[config] URL por defecto actualizada a {new_base}", flush=True)
    return jsonify({"url": new_base, "year": year, "contest": contest})


def _warmup():
    """Precalienta el caché al arrancar para que el primer request no espere."""
    import time as _t
    _t.sleep(2)  # espera mínima a que Flask esté listo
    try:
        print("[warmup] precalentando caché...", flush=True)
        _get_data(_config["base"])
        print("[warmup] caché listo", flush=True)
    except Exception as e:
        print(f"[warmup] falló (se reintentará en el primer request): {e}", flush=True)


threading.Thread(target=_warmup, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3001)))
