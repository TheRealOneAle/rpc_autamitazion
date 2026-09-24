from flask import Flask, jsonify, send_file, request
import os
import re
import requests
from io import BytesIO

app = Flask(__name__)


def _to_url(val, default):
    if not val:
        return default
    return val if val.startswith("http") else f"https://{val}"


BD_SERVICE_URL = _to_url(os.environ.get("BD_SERVICE_URL"), "http://boca-scraper:3001")
GLOBOS_SERVICE_URL = _to_url(os.environ.get("GLOBOS_SERVICE_URL"), "http://generarglobos:5000")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')

FALLBACK_COLORS = [
    '#FF8C94', '#8B0000', '#FF00FF', '#C8C8C8',
    '#006400', '#FF0000', '#32CD32', '#AAAAAA',
    '#FFD700', '#0000FF', '#111111', '#0055CC', '#FF8C00',
]

COUNTRY_NAMES = {
    'CO': 'Colombia', 'MX': 'México', 'PE': 'Perú',
    'AR': 'Argentina', 'CL': 'Chile', 'EC': 'Ecuador',
    'BO': 'Bolivia', 'VE': 'Venezuela', 'CR': 'Costa Rica',
    'PA': 'Panamá', 'BR': 'Brasil', 'CU': 'Cuba',
    'DO': 'República Dominicana', 'GT': 'Guatemala',
    'SV': 'El Salvador', 'HN': 'Honduras', 'NI': 'Nicaragua',
    'PY': 'Paraguay', 'UY': 'Uruguay',
}


def _contest_params():
    """Devuelve (year, contest, country, university, top_n, rpc_name, datetime_str) desde query params o JSON body."""
    data = {}
    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    year = str(request.args.get("year") or data.get("year") or "").strip()
    contest = str(request.args.get("contest") or data.get("contest") or "").strip()
    country = str(request.args.get("country") or data.get("country") or "").strip()
    univ = str(request.args.get("university") or data.get("university") or "").strip()
    top_n_raw = str(request.args.get("top_n") or request.args.get("limit") or data.get("top_n") or "").strip()
    rpc_name = str(request.args.get("rpc_name") or data.get("rpc_name") or "").strip()
    datetime_str = str(request.args.get("datetime_str") or data.get("datetime_str") or "").strip()

    if "/" in contest:
        parts = contest.split("/")
        year = parts[0].strip()
        contest = parts[1].strip()

    top_n = int(top_n_raw) if top_n_raw.isdigit() and int(top_n_raw) > 0 else 10

    if not rpc_name:
        if contest:
            c_clean = ''.join(c for c in str(contest) if c.isdigit())
            rpc_name = f"RPC {str(int(c_clean)).zfill(2)}" if c_clean else "RPC"
        else:
            rpc_name = "RPC"

    if not datetime_str:
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            bogota_tz = ZoneInfo('America/Bogota')
        except ImportError:
            from datetime import timezone, timedelta
            bogota_tz = timezone(timedelta(hours=-5))
        datetime_str = datetime.now(bogota_tz).strftime("%d/%m/%Y %H:%M")

    return year, contest, country, univ, top_n, rpc_name, datetime_str


def _file_key(year, contest, country=None, univ=None, top_n=10):
    parts = []
    if year and contest:
        parts.append(f"{year}_{str(int(contest)).zfill(2)}")
    else:
        parts.append("default")

    if country:
        parts.append(country.lower().replace(" ", "_"))
    elif univ:
        parts.append(re.sub(r'[^a-zA-Z0-9]', '', univ.lower())[:10])
    else:
        parts.append("latam")

    parts.append(f"top{top_n}")
    return "_".join(parts)


def _bd_url(base, path, year, contest, country=None, univ=None, top_n=None):
    url = f"{base}{path}"
    params = []
    if year and contest:
        params.append(f"contest={year}%2F{str(int(contest)).zfill(2)}")
    if country:
        params.append(f"country={country}")
    if univ:
        params.append(f"university={univ}")
    if top_n:
        params.append(f"top_n={top_n}")

    if params:
        url += ("&" if "?" in url else "?") + "&".join(params)
    return url


def _globo_img_html(globos_dir, letter_idx, balloon_size=26):
    """Returns an <img> with base64 data URI if the PNG exists, else a CSS balloon shape."""
    import base64
    path = os.path.join(globos_dir, f'{chr(65 + letter_idx)}.png')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" class="balloon" style="width:{balloon_size}px;">'
    color = FALLBACK_COLORS[letter_idx % len(FALLBACK_COLORS)]
    return (
        f'<span style="display:inline-block;width:{int(balloon_size*0.75)}px;height:{balloon_size}px;'
        f'background:{color};border-radius:50% 50% 50% 50%/60% 60% 40% 40%;'
        f'border:1px solid rgba(0,0,0,0.25);"></span>'
    )


def _ensure_globos(cantidadProblemas, year=None, contest=None):
    """Downloads balloon images from GLOBOS_SERVICE_URL to /tmp/globosgenerados/{file_key}/."""
    contest_key = f"{year}_{str(int(contest)).zfill(2)}" if year and contest else "default"
    tmp_dir = os.path.join('/tmp/globosgenerados', contest_key)
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        gen_url = _bd_url(GLOBOS_SERVICE_URL, "/generate", year, contest)
        requests.post(gen_url, timeout=30)
    except Exception as e:
        print(f"[warn] pre-generación de globos: {e}", flush=True)

    try:
        for i in range(cantidadProblemas):
            letter = chr(65 + i)
            dest = os.path.join(tmp_dir, f'{letter}.png')
            globo_url = _bd_url(GLOBOS_SERVICE_URL, f"/globo/{letter}.png", year, contest)
            r = requests.get(globo_url, timeout=20)
            if r.status_code == 200:
                with open(dest, 'wb') as f:
                    f.write(r.content)
        return tmp_dir
    except Exception as e:
        print(f"[warn] no se pudo descargar globos de {GLOBOS_SERVICE_URL}: {e}", flush=True)
        return '/app/globosgenerados'


def _build_elastic_css(top_n=10, row_count=10):
    """Genera reglas CSS elásticas para dimensionar la tabla según el tamaño del Top."""
    if row_count <= 5:
        th_pad = "14px 8px"
        td_pad = "12px 6px"
        team_font = "1.05rem"
        pts_font = "1.05rem"
        table_width = "95%"
        flag_size = "26px"
        page_height = "1300px"
        prob_w = "42px"
        cred_font = "0.74rem"
    elif row_count <= 10:
        th_pad = "10px 6px"
        td_pad = "7px 5px"
        team_font = "0.95rem"
        pts_font = "0.95rem"
        table_width = "97%"
        flag_size = "22px"
        page_height = "1650px"
        prob_w = "36px"
        cred_font = "0.72rem"
    elif row_count <= 15:
        th_pad = "8px 4px"
        td_pad = "5px 4px"
        team_font = "0.85rem"
        pts_font = "0.85rem"
        table_width = "98%"
        flag_size = "19px"
        page_height = "1950px"
        prob_w = "32px"
        cred_font = "0.71rem"
    else:  # top 20+
        th_pad = "6px 3px"
        td_pad = "3px 3px"
        team_font = "0.76rem"
        pts_font = "0.76rem"
        table_width = "99%"
        flag_size = "16px"
        page_height = "2250px"
        prob_w = "28px"
        cred_font = "0.70rem"

    return f"""
@page {{ size: 1100px {page_height}; margin: 0; }}
html, body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: #f4f6f7;
    margin: 0;
    padding: 15px;
    box-sizing: border-box;
}}
.cabecera-wrap {{
    width: 100%;
    margin: 0 auto 12px auto;
    text-align: center;
}}
.cabecera-tabla {{
    display: inline-table;
    border-collapse: collapse;
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
    margin: 0 auto !important;
    width: auto !important;
}}
.cabecera-tabla td {{
    border: none !important;
    padding: 0 !important;
    background: transparent !important;
    vertical-align: middle;
}}
.cabecera-td-logo {{
    padding-right: 22px !important;
    vertical-align: middle;
}}
.cabecera-td-textos {{
    text-align: left;
    vertical-align: middle;
}}
.logorpc {{
    width: 135px;
    display: block;
}}
.cabecera-titulo {{
    color: #1a1a1a;
    font-size: 1.7rem;
    font-weight: 800;
    margin: 0 0 6px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    line-height: 1.2;
    white-space: nowrap;
}}
.cabecera-meta {{
    margin: 0;
    padding: 0;
    line-height: 1.2;
    white-space: nowrap;
}}
.rpc-badge {{
    display: inline-block;
    background-color: #CF1F4A;
    color: #ffffff;
    font-size: 0.8rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 12px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    vertical-align: middle;
}}
.rpc-datetime {{
    display: inline-block;
    color: #475569;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.2px;
    margin-left: 12px;
    vertical-align: middle;
}}
.cal-icon {{
    display: inline-block;
    vertical-align: -2px;
    margin-right: 4px;
    width: 14px;
    height: 14px;
}}
table.tabla-ranking {{
    border-collapse: collapse;
    margin: 8px auto;
    width: {table_width};
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}}
table.tabla-ranking th {{
    background-color: #CF1F4A;
    color: white;
    padding: {th_pad};
    font-size: 0.92rem;
    font-weight: 600;
    text-align: center;
}}
table.tabla-ranking td {{
    vertical-align: middle;
    padding: {td_pad};
    border-bottom: 1px solid #eaeaea;
}}
.col-num {{
    text-align: center;
    font-weight: 700;
    font-size: {pts_font};
    width: 36px;
}}
.col-team {{
    width: auto;
}}
.col-prob {{
    width: {prob_w};
    max-width: {prob_w};
    text-align: center;
    padding: 2px !important;
}}
.col-total {{
    text-align: center;
    white-space: nowrap;
    font-weight: 700;
    font-size: {pts_font};
    width: 85px;
}}
.numequipo {{
    text-align: center;
    font-weight: 700;
    font-size: {pts_font};
}}
.puntos {{
    text-align: center;
    white-space: nowrap;
    font-weight: 700;
    font-size: {pts_font};
}}
.problemTeam {{
    text-align: center;
    padding: 2px;
    line-height: 1;
}}
tr:nth-child(even) {{ background-color: #fafbfc; }}
.balloon {{ height: auto; vertical-align: middle; }}
.flag {{
    width: {flag_size};
    height: {flag_size};
    border-radius: 50%;
    vertical-align: middle;
    flex-shrink: 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}}
.team-col {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: {team_font};
    font-weight: 600;
    color: #2c3e50;
    max-width: 480px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.univ-sub {{
    font-size: 0.72rem;
    color: #7f8c8d;
    font-weight: 400;
    display: block;
    margin-top: 1px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.pie-creditos {{
    width: {table_width};
    margin: 6px auto 0 auto;
    text-align: right;
    color: #64748b;
    font-size: {cred_font};
    font-weight: 500;
    letter-spacing: 0.2px;
    padding-right: 4px;
    box-sizing: border-box;
}}
"""


def _ranking_html(rows, cantidadProblemas, problemasTeam, titulo="Top 10 Latinoamérica", globos_dir='/app/globosgenerados', top_n=10, rpc_name="RPC", datetime_str=""):
    headers = "".join(f'<th class="col-prob">{chr(65 + i)}</th>' for i in range(cantidadProblemas))
    rows_html = ""
    row_count = len(rows)
    balloon_size = 30 if row_count <= 5 else (25 if row_count <= 10 else (20 if row_count <= 15 else 17))

    clean_dt = str(datetime_str or "").replace("📅", "").strip()
    clean_dt = re.sub(r'(?i)\bhora de bogot[aá]\b', 'Hora de Colombia', clean_dt).strip()
    if not clean_dt:
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            bogota_tz = ZoneInfo('America/Bogota')
        except ImportError:
            from datetime import timezone, timedelta
            bogota_tz = timezone(timedelta(hours=-5))
        clean_dt = datetime.now(bogota_tz).strftime("%d/%m/%Y %H:%M")

    if "colombia" not in clean_dt.lower() and "hora" not in clean_dt.lower():
        display_datetime = f"{clean_dt} Hora de Colombia"
    else:
        display_datetime = clean_dt

    for i, r in enumerate(rows):
        if i == 0:
            style = 'style="background-color:#FFF673;"'  # Oro
        elif i == 1:
            style = 'style="background-color:#9FCDD6;"'  # Plata
        elif i == 2:
            style = 'style="background-color:#80C491;"'  # Bronce
        else:
            style = ""

        problemasHtml = ""
        for j in range(cantidadProblemas):
            solved = (i < len(problemasTeam) and j < len(problemasTeam[i]) and problemasTeam[i][j] == 1)
            if solved:
                problemasHtml += f'<td class="problemTeam col-prob">{_globo_img_html(globos_dir, j, balloon_size=balloon_size)}</td>'
            else:
                problemasHtml += '<td class="problemTeam col-prob" style="text-align:center;color:#ccc;">-</td>'

        pos_display = r.get("pos", i + 1)
        country = (r.get("country") or "").upper()
        flag_file = f"/app/flags/{country.lower()}.svg" if country else ""
        flag_html = f'<img src="file://{flag_file}" class="flag">' if country and os.path.exists(flag_file) else ""

        univ_name = r.get("university") or r.get("university_normalized") or ""
        univ_html = f'<span class="univ-sub">{univ_name}</span>' if univ_name and univ_name != "Desconocida" else ""

        rows_html += f"""
    <tr {style}>
        <td class="numequipo col-num">{pos_display}</td>
        <td class="col-team">
            <div class="team-col">
                {flag_html}
                <div>
                    <div>{r['userfullname']}</div>
                    {univ_html}
                </div>
            </div>
        </td>
        {problemasHtml}
        <td class="puntos col-total">{r['problemas_resueltos']} ({r['points']})</td>
    </tr>"""

    css = _build_elastic_css(top_n=top_n, row_count=row_count)
    return f"""<html>
<head><meta charset="utf-8"><style>{css}</style></head>
<body>
<div class="cabecera-wrap">
    <table class="cabecera-tabla">
        <tr>
            <td class="cabecera-td-logo">
                <img src="file:///app/logorpc/rpc.png" class="logorpc">
            </td>
            <td class="cabecera-td-textos">
                <div class="cabecera-titulo">{titulo}</div>
                <div class="cabecera-meta">
                    <span class="rpc-badge">{rpc_name}</span>
                    <span class="rpc-datetime"><svg class="cal-icon" viewBox="0 0 24 24"><path fill="#64748b" d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z"/></svg>{display_datetime}</span>
                </div>
            </td>
        </tr>
    </table>
</div>
<table class="tabla-ranking">
<tr><th class="col-num">#</th><th class="col-team">Equipo</th>{headers}<th class="col-total">Total</th></tr>
{rows_html}
</table>
<div class="pie-creditos">Creado por @trueyalejo @j_gab_torres</div>
</body>
</html>"""


def _screenshot_html(html_content, output_path=None):
    """Renders HTML to JPEG via weasyprint."""
    from weasyprint import HTML
    from PIL import Image

    png_bytes = HTML(string=html_content, base_url='/').write_png()
    img = Image.open(BytesIO(png_bytes)).convert('RGB')

    # Auto-crop background color from bottom
    bg = (244, 246, 247)
    w, h = img.size
    crop_y = h
    step = max(w // 20, 1)
    for y in range(h - 1, 0, -1):
        sample = [img.getpixel((x, y)) for x in range(0, w, step)]
        if not all(
            abs(p[0] - bg[0]) < 15 and abs(p[1] - bg[1]) < 15 and abs(p[2] - bg[2]) < 15
            for p in sample
        ):
            crop_y = min(y + 35, h)
            break
    img = img.crop((0, 0, w, crop_y))

    if output_path:
        img.save(output_path, 'JPEG', quality=88)
        return None
    else:
        buf = BytesIO()
        img.save(buf, 'JPEG', quality=88)
        return buf.getvalue()


def generate_ranking(year, contest, country=None, univ=None, top_n=10, rpc_name=None, datetime_str=None):
    file_key = _file_key(year, contest, country=country, univ=univ, top_n=top_n)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not rpc_name:
        if contest:
            c_clean = ''.join(c for c in str(contest) if c.isdigit())
            rpc_name = f"RPC {str(int(c_clean)).zfill(2)}" if c_clean else "RPC"
        else:
            rpc_name = "RPC"

    if not datetime_str:
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            bogota_tz = ZoneInfo('America/Bogota')
        except ImportError:
            from datetime import timezone, timedelta
            bogota_tz = timezone(timedelta(hours=-5))
        datetime_str = datetime.now(bogota_tz).strftime("%d/%m/%Y %H:%M")

    # 1. Fetch ranking con filtros aplicados
    try:
        rank_url = _bd_url(BD_SERVICE_URL, "/api/ranking", year, contest, country=country, univ=univ, top_n=top_n)
        response = requests.get(rank_url, timeout=12)
        if response.status_code != 200:
            raise Exception(f"Error obteniendo ranking: {response.text}")
        data = response.json()
        if not data.get("success"):
            raise Exception(f"Error en la respuesta: {data.get('error')}")
        rows = data["rows"]
        cantidadProblemas = data["cantidadProblemas"]
    except Exception as e:
        raise Exception(f"Error comunicación con servicio bd: {e}")

    # 2. Fetch AC runs
    try:
        ac_url = _bd_url(BD_SERVICE_URL, "/api/teams/ac", year, contest)
        response = requests.get(ac_url, timeout=12)
        if response.status_code != 200:
            raise Exception(f"Error obteniendo AC runs: {response.text}")
        ac_data = response.json()
        if not ac_data.get("success"):
            raise Exception(f"Error en la respuesta AC: {ac_data.get('error')}")
        teamsAC = [(r["usernumber"], r["runproblem"]) for r in ac_data["rows"]]
    except Exception as e:
        raise Exception(f"Error comunicación con servicio bd (AC): {e}")

    # 3. Mapear AC por fila del ranking mostrado
    teams = [row["usernumber"] for row in rows]
    teamsIndex = {team: i for i, team in enumerate(teams)}
    problemasTeam = [[0] * cantidadProblemas for _ in range(len(rows))]

    for team, problem in teamsAC:
        if team in teamsIndex:
            i = teamsIndex[team]
            j = problem - 1
            if 0 <= j < cantidadProblemas:
                problemasTeam[i][j] = 1

    # 4. Título dinámico
    if country:
        c_name = COUNTRY_NAMES.get(country.upper(), country.capitalize())
        titulo = f"Top {len(rows)} {c_name}"
    elif univ:
        titulo = f"Top {len(rows)} {univ}"
    else:
        titulo = f"Top {len(rows)} Latinoamérica"

    # 5. Generar HTML y renderizar imagen
    globos_dir = _ensure_globos(cantidadProblemas, year=year, contest=contest)
    html = _ranking_html(rows, cantidadProblemas, problemasTeam, titulo=titulo, globos_dir=globos_dir, top_n=top_n, rpc_name=rpc_name, datetime_str=datetime_str)
    
    html_path = os.path.join(OUTPUT_DIR, f"ranking_{file_key}.html")
    jpg_path = os.path.join(OUTPUT_DIR, f"ranking_{file_key}.jpg")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    _screenshot_html(html, jpg_path)

    return file_key, jpg_path


@app.route('/generate', methods=['POST'])
def generate():
    year, contest, country, univ, top_n, rpc_name, datetime_str = _contest_params()
    try:
        file_key, jpg_path = generate_ranking(year, contest, country=country, univ=univ, top_n=top_n, rpc_name=rpc_name, datetime_str=datetime_str)
        return jsonify({
            "status": "success",
            "message": "Tabla generada exitosamente",
            "file": f"ranking_{file_key}.jpg",
            "path": jpg_path,
            "top_n": top_n,
            "country": country,
            "rpc_name": rpc_name,
            "datetime_str": datetime_str,
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ranking.jpg', methods=['GET'])
def get_image():
    year, contest, country, univ, top_n, rpc_name, datetime_str = _contest_params()
    file_key = _file_key(year, contest, country=country, univ=univ, top_n=top_n)
    path = os.path.join(OUTPUT_DIR, f"ranking_{file_key}.jpg")

    if not os.path.exists(path):
        try:
            _, path = generate_ranking(year, contest, country=country, univ=univ, top_n=top_n, rpc_name=rpc_name, datetime_str=datetime_str)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    try:
        return send_file(path, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 404


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5002)))
