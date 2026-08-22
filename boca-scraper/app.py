import hashlib
import os
import re
import threading
import time

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

from university_normalizer import (
    normalize_university,
    normalize_country_code,
    get_country_name,
    COUNTRY_NAMES,
    TRUSTED_FLAGS,
)

app = Flask(__name__)

_BASE_DEFAULT = os.environ.get("BOCA_URL", "https://redprogramacioncompetitiva.com/contests/2026/06")
BOCA_USER = os.environ.get("BOCA_USER", "silux")
BOCA_PASS = os.environ.get("BOCA_PASS", "ovallos.")
CACHE_TTL = int(os.environ.get("CACHE_TTL", "45"))

# URL mutable en tiempo de ejecución (cambia con POST /config)
_config = {"base": _BASE_DEFAULT}

# Caché por contest: {contest_key: {"teams":..., "colors":..., "runs":..., "ts":...}}
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


def _parse_year_contest_from_base(base):
    m = re.search(r"/contests/(\d{4})/(\d{1,2})", base or "")
    if m:
        return m.group(1), m.group(2)
    return None, None


def _fetch_problems_from_db(year=None, contest=None):
    """Opción 1: Consulta directa a la base de datos PostgreSQL de BOCA (problemtable)."""
    db_host = os.environ.get("BOCA_DB_HOST")
    if not db_host:
        return None

    if year and contest:
        target_db = f"rpc_{year}_{str(int(contest)).zfill(2)}"
    else:
        target_db = os.environ.get("BOCA_DB_NAME", "bkboca")

    db_candidates = [target_db]
    env_db = os.environ.get("BOCA_DB_NAME")
    if env_db and env_db not in db_candidates:
        db_candidates.append(env_db)
    if "bkboca" not in db_candidates:
        db_candidates.append("bkboca")

    for db_name in db_candidates:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=db_host,
                port=int(os.environ.get("BOCA_DB_PORT", "5432")),
                dbname=db_name,
                user=os.environ.get("BOCA_DB_USER", "postgres"),
                password=os.environ.get("BOCA_DB_PASS", "1234"),
                connect_timeout=5,
            )
            try:
                with conn.cursor() as cur:
                    contest_num = os.environ.get("BOCA_CONTEST_NUMBER") or (str(int(contest)) if contest else None)
                    rows = []
                    if contest_num:
                        try:
                            cur.execute(
                                "SELECT problemnumber, problemname, problemcolor, problemcolorname "
                                "FROM problemtable WHERE contestnumber = %s ORDER BY problemnumber ASC",
                                (contest_num,)
                            )
                            rows = cur.fetchall()
                        except Exception:
                            conn.rollback()

                    if not rows:
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
                    if problems:
                        return problems
            finally:
                conn.close()
        except Exception as e:
            pass

    return None


def _fetch_problems_from_admin(base):
    """Opción 2: Scraping de admin/problem.php de BOCA."""
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
                continue
            p_name = cells[1].get_text(strip=True) if len(cells) > 1 else chr(64 + p_num)

            color_cell = cells[-1]
            color = None
            color_inp = color_cell.find("input", attrs={"name": re.compile(r"^color\d+$")})
            if color_inp and color_inp.get("value"):
                color = color_inp["value"].strip()
            if not color:
                img = color_cell.find("img")
                if img and img.get("title"):
                    color = img["title"].strip()
            if not color:
                cname_inp = color_cell.find("input", attrs={"name": re.compile(r"^colorname\d+$")})
                if cname_inp and cname_inp.get("value") and cname_inp["value"] != "Can be empty":
                    color = cname_inp["value"].strip()

            norm_color = _normalize_color(color) or DEFAULT_COLORS[(p_num - 1) % len(DEFAULT_COLORS)]
            problems.append((p_num, p_name, norm_color))

        return problems if problems else None
    except Exception as e:
        print(f"[scraper] advertencia: error al scrapear admin/problem.php: {e}", flush=True)
        return None


def _login_and_fetch(base):
    auth_candidates = [
        ("board", ""),
        (BOCA_USER, BOCA_PASS),
        ("score", ""),
    ]

    last_err = None
    for user, pwd in auth_candidates:
        try:
            session = requests.Session()
            session.get(f"{base}/index.php", timeout=15)
            sid = session.cookies.get("PHPSESSID", "")
            pass_hash = _hash(_hash(pwd or "") + sid)
            session.get(
                f"{base}/index.php",
                params={"name": user, "password": pass_hash},
                timeout=15,
            )
            for path in ["score/score.php", "admin/score.php", "score.php"]:
                resp = session.get(f"{base}/{path}", timeout=15)
                if resp.status_code == 200 and "Session expired" not in resp.text:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    tables = soup.find_all("table")
                    if len(tables) >= 3:
                        return resp.text
        except Exception as e:
            last_err = e
            continue

    raise ValueError(f"No se pudo obtener la tabla de score para {base}: {last_err or 'No se encontraron tablas válidas'}")


def _extract_color(cell):
    color = cell.get("bgcolor") or ""
    if not color:
        m = re.search(r"background(?:-color)?:\s*(#[0-9a-fA-F]{3,6})", cell.get("style", ""))
        color = m.group(1) if m else ""
    return _normalize_color(color) or None


def _is_solved(cell_text):
    if not cell_text or cell_text in ("-", "---", "\u2026"):
        return False
    return bool(re.search(r"\d+/\d+", cell_text))


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
    problem_col_start = 2
    teams = []
    seen_names = set()
    header_found = False
    has_university_col = False

    for row in rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(strip=True) for c in cells]
        if not texts:
            continue

        if texts[0] in ("#", "Pos", "Rank") and not header_found:
            header_found = True
            for col_idx, cell in enumerate(cells):
                t = cell.get_text(strip=True)
                if t.lower() in ("university", "universidad", "institucion", "institución"):
                    has_university_col = True
                if len(t) == 1 and t.isupper():
                    if not problem_colors:
                        problem_col_start = col_idx
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
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Flag and country
        flag_img = cells[1].find("img") if len(cells) > 1 else None
        raw_country = flag_img.get("alt", "").strip() if flag_img else ""
        
        # University extraction
        raw_univ = ""
        if has_university_col and len(texts) > 2:
            raw_univ = texts[2]
        
        # Normalization
        univ_info = normalize_university(raw_univ, existing_country=raw_country)
        country_code = normalize_country_code(raw_country) or univ_info.get("country_code", "CO")
        country_name = get_country_name(country_code)

        n = len(problem_colors)
        solved_problems = []

        for i in range(n):
            cidx = problem_col_start + i
            if cidx < len(texts) and _is_solved(texts[cidx]):
                solved_problems.append(i + 1)

        n_solved, penalty = _parse_total(texts[-1] if texts else "")
        if n_solved is None:
            n_solved = len(solved_problems)
            penalty = 0

        teams.append({
            "pos": len(teams) + 1,
            "usernumber": pos,
            "userfullname": name,
            "university": raw_univ or univ_info["name"],
            "university_normalized": univ_info["name"],
            "university_acronym": univ_info["acronym"],
            "country": country_code,
            "country_name": country_name,
            "problemas_resueltos": n_solved,
            "points": penalty,
            "solved_problems": solved_problems,
        })

    return teams, problem_colors


def _fetch_runs_from_boca(base):
    """Obtiene los envíos en tiempo real desde admin/run.php."""
    session = requests.Session()
    session.get(f"{base}/index.php", timeout=15)
    sid = session.cookies.get("PHPSESSID", "")
    pass_hash = _hash(_hash(BOCA_PASS) + sid)
    session.get(
        f"{base}/index.php",
        params={"name": BOCA_USER, "password": pass_hash},
        timeout=15,
    )
    resp = session.get(f"{base}/admin/run.php", timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 3:
        return []

    table = tables[2]
    rows = table.find_all("tr")
    runs = []
    for r in rows:
        cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
        if len(cells) >= 10 and cells[0].isdigit():
            run_num = int(cells[0])
            site = int(cells[1]) if cells[1].isdigit() else 1
            user = cells[2]
            time_min = int(cells[3]) if cells[3].isdigit() else 0
            problem = cells[4].upper()
            lang = cells[5]
            verdict = cells[9]
            is_solved = verdict.startswith("YES")

            runs.append({
                "run_number": run_num,
                "site": site,
                "username": user,
                "time_minutes": time_min,
                "letter": problem,
                "language": lang,
                "verdict": verdict,
                "is_solved": is_solved,
            })
    return runs


def _get_data(base, force_fresh=False):
    key = _contest_key(base)
    now = time.time()

    if not force_fresh:
        with _lock:
            cache = _caches.get(key)
            if cache is not None and now - cache.get("ts", 0) <= CACHE_TTL:
                return cache["teams"], cache["colors"]

    try:
        html = _login_and_fetch(base)
        teams, color_list = _parse(html)

        year, contest = _parse_year_contest_from_base(base)
        admin_problems = _fetch_problems_from_db(year, contest) or _fetch_problems_from_admin(base)
        if admin_problems:
            color_list = admin_problems

        with _lock:
            _caches[key] = {
                "teams": teams,
                "colors": color_list,
                "ts": time.time(),
            }
        return teams, color_list
    except Exception as e:
        print(f"[scraper] error al obtener datos de {key}: {e}", flush=True)
        cache = _caches.get(key)
        if cache is not None:
            return cache["teams"], cache["colors"]
        raise


def _get_runs_data(base, force_fresh=False):
    key = _contest_key(base)
    now = time.time()

    if not force_fresh:
        with _lock:
            cache = _caches.get(key)
            if cache is not None and "runs" in cache and now - cache.get("runs_ts", 0) <= CACHE_TTL:
                return cache["runs"]

    try:
        runs = _fetch_runs_from_boca(base)
        with _lock:
            if key not in _caches:
                _caches[key] = {}
            _caches[key]["runs"] = runs
            _caches[key]["runs_ts"] = time.time()
        return runs
    except Exception as e:
        print(f"[scraper] error al obtener runs de {key}: {e}", flush=True)
        with _lock:
            cache = _caches.get(key)
            if cache and "runs" in cache:
                return cache["runs"]
        return []


def _filter_teams(teams, country_filter=None, univ_filter=None):
    filtered = teams
    if country_filter:
        norm_c = normalize_country_code(country_filter)
        if norm_c:
            filtered = [t for t in filtered if t.get("country") == norm_c]
        else:
            c_low = country_filter.strip().lower()
            filtered = [t for t in filtered if c_low in (t.get("country_name") or "").lower()]

    if univ_filter:
        u_low = univ_filter.strip().lower()
        filtered = [
            t for t in filtered
            if u_low in (t.get("university_normalized") or "").lower()
            or u_low in (t.get("university_acronym") or "").lower()
            or u_low in (t.get("university") or "").lower()
        ]

    # Re-enumerar posición pos dentro del filtro manteniendo su usernumber
    result = []
    for idx, t in enumerate(filtered):
        item = dict(t)
        item["pos"] = idx + 1
        result.append(item)
    return result


# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.route("/api/teams", methods=["GET"])
def get_teams():
    try:
        base, _ = _base_from_request()
        teams, _ = _get_data(base)
        country = request.args.get("country")
        univ = request.args.get("university")
        filtered = _filter_teams(teams, country, univ)
        rows = [
            {
                "usernumber": t["usernumber"],
                "userfullname": t["userfullname"],
                "country": t["country"],
                "country_name": t.get("country_name"),
                "university": t.get("university_normalized"),
                "university_acronym": t.get("university_acronym"),
            }
            for t in filtered
        ]
        return jsonify({"success": True, "rows": rows, "total": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/problems", methods=["GET"])
def get_problems():
    try:
        base, _ = _base_from_request()
        year, contest = _parse_year_contest_from_base(base)
        fresh_problems = _fetch_problems_from_db(year, contest) or _fetch_problems_from_admin(base)
        if fresh_problems:
            colors = fresh_problems
        else:
            _, colors = _get_data(base, force_fresh=True)

        rows = [
            {
                "problemnumber": item[0],
                "problemletter": chr(64 + item[0]),
                "problemname": item[1] if len(item) > 1 else chr(64 + item[0]),
                "problemcolor": item[2] if len(item) > 2 else item[1],
            }
            for item in colors
        ]
        return jsonify({"success": True, "rows": rows, "count": len(rows)})
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

        country = request.args.get("country")
        univ = request.args.get("university")
        top_n_param = request.args.get("top_n") or request.args.get("limit")
        top_n = int(top_n_param) if top_n_param and top_n_param.isdigit() else 10

        filtered = _filter_teams(teams, country, univ)
        sliced = filtered[:top_n]

        rows = [
            {
                "pos": t["pos"],
                "userfullname": t["userfullname"],
                "country": t["country"],
                "country_name": t.get("country_name"),
                "university": t.get("university_normalized"),
                "university_acronym": t.get("university_acronym"),
                "usernumber": t["usernumber"],
                "problemas_resueltos": t["problemas_resueltos"],
                "points": t["points"],
            }
            for t in sliced
        ]
        return jsonify({
            "success": True,
            "rows": rows,
            "cantidadProblemas": len(colors),
            "contest": key,
            "top_n": top_n,
            "filter_country": country,
            "filter_university": univ,
            "total_participating": len(filtered),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ranking/full", methods=["GET"])
def get_ranking_full():
    try:
        base, key = _base_from_request()
        teams, colors = _get_data(base)

        country = request.args.get("country")
        univ = request.args.get("university")
        filtered = _filter_teams(teams, country, univ)

        rows = [
            {
                "pos": t["pos"],
                "userfullname": t["userfullname"],
                "country": t["country"],
                "country_name": t.get("country_name"),
                "university": t.get("university_normalized"),
                "university_acronym": t.get("university_acronym"),
                "usernumber": t["usernumber"],
                "problemas_resueltos": t["problemas_resueltos"],
                "points": t["points"],
            }
            for t in filtered
        ]
        return jsonify({
            "success": True,
            "rows": rows,
            "cantidadProblemas": len(colors),
            "contest": key,
            "total": len(rows),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/countries", methods=["GET"])
def get_countries():
    """Retorna los países presentes en el concurso actual con estadísticas de participación."""
    try:
        base, key = _base_from_request()
        teams, _ = _get_data(base)

        counts = {}
        for t in teams:
            c_code = t.get("country") or "UNKNOWN"
            c_name = t.get("country_name") or get_country_name(c_code)
            if c_code not in counts:
                counts[c_code] = {"code": c_code, "name": c_name, "teams_count": 0}
            counts[c_code]["teams_count"] += 1

        countries_list = sorted(counts.values(), key=lambda x: (-x["teams_count"], x["name"]))
        return jsonify({
            "success": True,
            "contest": key,
            "countries": countries_list,
            "total_countries": len(countries_list),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/universities", methods=["GET"])
def get_universities():
    """Retorna las universidades presentes en el concurso actual."""
    try:
        base, key = _base_from_request()
        teams, _ = _get_data(base)
        country = request.args.get("country")
        filtered = _filter_teams(teams, country)

        unis = {}
        for t in filtered:
            uname = t.get("university_normalized") or "Desconocida"
            if uname not in unis:
                unis[uname] = {
                    "name": uname,
                    "acronym": t.get("university_acronym", "N/A"),
                    "country": t.get("country"),
                    "country_name": t.get("country_name"),
                    "teams_count": 0,
                }
            unis[uname]["teams_count"] += 1

        uni_list = sorted(unis.values(), key=lambda x: (-x["teams_count"], x["name"]))
        return jsonify({
            "success": True,
            "contest": key,
            "universities": uni_list,
            "total_universities": len(uni_list),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/runs", methods=["GET"])
def get_runs():
    """Retorna la lista de envíos de la competencia actual."""
    try:
        base, key = _base_from_request()
        runs = _get_runs_data(base)
        return jsonify({
            "success": True,
            "contest": key,
            "runs": runs,
            "total_runs": len(runs),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/first-solutions", methods=["GET"])
def get_first_solutions():
    """Retorna el primer envío aceptado (First Solution) para cada problema de la maratón."""
    try:
        base, key = _base_from_request()
        runs = _get_runs_data(base)
        teams, colors = _get_data(base)

        # Mapa de colores y nombres de problemas
        color_map = {}
        name_map = {}
        for item in colors:
            p_num = item[0]
            letter = chr(64 + p_num)
            p_name = item[1] if len(item) > 1 else letter
            p_color = item[2] if len(item) > 2 else DEFAULT_COLORS[(p_num - 1) % len(DEFAULT_COLORS)]
            color_map[letter] = p_color
            name_map[letter] = p_name

        # Mapa de equipos por username / userfullname
        team_map = {}
        for t in teams:
            team_map[t["userfullname"].lower()] = t
            team_map[f"team{t['usernumber']}"] = t

        # Encontrar primer AC por letra
        first_solutions = {}
        for r in runs:
            if r["is_solved"]:
                let = r["letter"].upper()
                curr_min = r["time_minutes"]
                if let not in first_solutions or curr_min < first_solutions[let]["time_minutes"]:
                    u_key = r["username"].lower()
                    team_info = team_map.get(u_key, {})
                    first_solutions[let] = {
                        "problem_letter": let,
                        "problem_name": name_map.get(let, let),
                        "problem_color": color_map.get(let, DEFAULT_COLORS[0]),
                        "run_number": r["run_number"],
                        "username": r["username"],
                        "team_name": team_info.get("userfullname") or r["username"],
                        "university": team_info.get("university_normalized") or team_info.get("university") or "RPC",
                        "university_acronym": team_info.get("university_acronym", "N/A"),
                        "country_code": team_info.get("country") or "CO",
                        "country_name": team_info.get("country_name") or "Latinoamérica",
                        "time_minutes": curr_min,
                        "language": r["language"],
                        "verdict": r["verdict"],
                    }

        result = [first_solutions[k] for k in sorted(first_solutions.keys())]
        return jsonify({
            "success": True,
            "contest": key,
            "first_solutions": result,
            "solved_problems_count": len(result),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Retorna estadísticas completas y detalladas de la competencia."""
    try:
        base, key = _base_from_request()
        teams, colors = _get_data(base)
        runs = _get_runs_data(base)

        total_teams = len(teams)
        teams_with_solved = sum(1 for t in teams if t["problemas_resueltos"] > 0)
        total_runs = len(runs)
        total_ac = sum(1 for r in runs if r["is_solved"])
        acceptance_rate = round((total_ac / total_runs * 100), 1) if total_runs > 0 else 0.0

        # Estadísticas por problema
        problem_stats = {}
        for item in colors:
            let = chr(64 + item[0])
            problem_stats[let] = {
                "letter": let,
                "name": item[1] if len(item) > 1 else let,
                "color": item[2] if len(item) > 2 else DEFAULT_COLORS[0],
                "total_submissions": 0,
                "accepted_submissions": 0,
                "acceptance_rate": 0.0,
                "first_solution": None,
            }

        verdicts_count = {}
        languages_count = {}

        for r in runs:
            let = r["letter"].upper()
            if let in problem_stats:
                problem_stats[let]["total_submissions"] += 1
                if r["is_solved"]:
                    problem_stats[let]["accepted_submissions"] += 1
                    curr_fs = problem_stats[let]["first_solution"]
                    if curr_fs is None or r["time_minutes"] < curr_fs["time_minutes"]:
                        problem_stats[let]["first_solution"] = {
                            "username": r["username"],
                            "time_minutes": r["time_minutes"],
                            "language": r["language"],
                        }

            # Contar veredictos
            v = r["verdict"]
            v_clean = "Accepted (YES)" if r["is_solved"] else (v.replace("NO - ", "").strip() or "Other")
            verdicts_count[v_clean] = verdicts_count.get(v_clean, 0) + 1

            # Contar lenguajes
            lang = r["language"] or "Unknown"
            languages_count[lang] = languages_count.get(lang, 0) + 1

        for let, stat in problem_stats.items():
            tot = stat["total_submissions"]
            ac = stat["accepted_submissions"]
            stat["acceptance_rate"] = round((ac / tot * 100), 1) if tot > 0 else 0.0

        # Problema más resuelto
        sorted_by_ac = sorted(problem_stats.values(), key=lambda x: -x["accepted_submissions"])
        most_solved = sorted_by_ac[0] if sorted_by_ac and sorted_by_ac[0]["accepted_submissions"] > 0 else None

        return jsonify({
            "success": True,
            "contest": key,
            "total_teams": total_teams,
            "teams_with_solved": teams_with_solved,
            "total_submissions": total_runs,
            "accepted_submissions": total_ac,
            "acceptance_rate": acceptance_rate,
            "most_solved_problem": most_solved,
            "problems": list(problem_stats.values()),
            "verdicts": verdicts_count,
            "languages": languages_count,
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
    import time as _t
    _t.sleep(2)
    try:
        print("[warmup] precalentando caché...", flush=True)
        _get_data(_config["base"])
        _get_runs_data(_config["base"])
        print("[warmup] caché listo", flush=True)
    except Exception as e:
        print(f"[warmup] falló: {e}", flush=True)


threading.Thread(target=_warmup, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3001)))
