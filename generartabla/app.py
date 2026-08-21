from flask import Flask, jsonify, send_file, request
import os
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

RANKING_CSS = """
@page { size: 1100px 2000px; margin: 0; }
html, body {
    font-family: Arial, sans-serif;
    background-color: #f4f6f7;
    margin: 0;
    padding: 20px;
    box-sizing: border-box;
}
.cabecera { display: flex; align-items: center; justify-content: center; gap: 15px; }
.logorpc { width: 150px; }
table {
    border-collapse: collapse;
    margin: 10px auto;
    width: 97%;
    background: white;
    border-radius: 10px;
    overflow: hidden;
}
th { background-color: #CF1F4A; color: white; padding: 12px; }
td { vertical-align: middle; }
.numequipo { text-align: center; }
.puntos { text-align: center; white-space: nowrap; }
.problemTeam { text-align: center; padding: 4px; }
tr:nth-child(even) { background-color: #f2f2f2; }
.balloon { width: 30px; height: auto; }
.flag { width: 25px; height: 25px; border-radius: 50%; vertical-align: middle; }
.team-col { display: flex; align-items: center; gap: 10px; padding: 8px 10px; }
"""

FALLBACK_COLORS = [
    '#FF8C94', '#8B0000', '#FF00FF', '#C8C8C8',
    '#006400', '#FF0000', '#32CD32', '#AAAAAA',
    '#FFD700', '#0000FF', '#111111', '#0055CC', '#FF8C00',
]


def _contest_params():
    """Devuelve (year, contest) desde query params. Soporta contest=YYYY/NN o year+contest."""
    year = (request.args.get("year") or "").strip()
    contest = (request.args.get("contest") or "").strip()
    if "/" in contest:
        parts = contest.split("/")
        year = parts[0].strip()
        contest = parts[1].strip()
    return year, contest


def _file_key(year, contest):
    if not year or not contest:
        return "default"
    return f"{year}_{str(int(contest)).zfill(2)}"


def _bd_url(base, path, year, contest):
    url = f"{base}{path}"
    if year and contest:
        url += f"?contest={year}%2F{str(int(contest)).zfill(2)}"
    return url


def _globo_img_html(globos_dir, letter_idx):
    """Returns an <img> with base64 data URI if the PNG exists, else a CSS balloon shape."""
    import base64
    path = os.path.join(globos_dir, f'{chr(65 + letter_idx)}.png')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" class="balloon">'
    color = FALLBACK_COLORS[letter_idx % len(FALLBACK_COLORS)]
    return (
        f'<span style="display:inline-block;width:22px;height:28px;'
        f'background:{color};border-radius:50% 50% 50% 50%/60% 60% 40% 40%;'
        f'border:1px solid rgba(0,0,0,0.25);"></span>'
    )


def _ensure_globos(cantidadProblemas, year=None, contest=None):
    """Downloads balloon images from GLOBOS_SERVICE_URL to /tmp/globosgenerados/{file_key}/.
    Falls back to /app/globosgenerados/ (may be empty — _globo_img_html handles that case)."""
    file_key = _file_key(year, contest) if year and contest else ""
    tmp_dir = os.path.join('/tmp/globosgenerados', file_key) if file_key else '/tmp/globosgenerados'
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        # Pre-warm: trigger generation in case the service is sleeping
        gen_url = _bd_url(GLOBOS_SERVICE_URL, "/generate", year, contest) if year and contest else f"{GLOBOS_SERVICE_URL}/generate"
        requests.post(gen_url, timeout=60)
    except Exception as e:
        print(f"[warn] pre-generación de globos: {e}", flush=True)
    try:
        for i in range(cantidadProblemas):
            letter = chr(65 + i)
            dest = os.path.join(tmp_dir, f'{letter}.png')
            if not os.path.exists(dest):
                globo_url = _bd_url(GLOBOS_SERVICE_URL, f"/globo/{letter}.png", year, contest) if year and contest else f"{GLOBOS_SERVICE_URL}/globo/{letter}.png"
                r = requests.get(globo_url, timeout=30)
                r.raise_for_status()
                with open(dest, 'wb') as f:
                    f.write(r.content)
        return tmp_dir
    except Exception as e:
        print(f"[warn] no se pudo descargar globos de {GLOBOS_SERVICE_URL}: {e}", flush=True)
        return '/app/globosgenerados'



def _ranking_html(rows, cantidadProblemas, problemasTeam, titulo="Top 10 Latinoamerica", globos_dir='/app/globosgenerados'):
    headers = "".join(f"<th>{chr(65 + i)}</th>" for i in range(cantidadProblemas))
    rows_html = ""
    for i, r in enumerate(rows):
        if i == 0:
            style = 'style="background-color:#FFF673;"'
        elif i == 1:
            style = 'style="background-color:#9FCDD6;"'
        elif i == 2:
            style = 'style="background-color:#80C491;"'
        else:
            style = ""

        problemasHtml = ""
        for j in range(cantidadProblemas):
            solved = (i < len(problemasTeam) and j < len(problemasTeam[i])
                      and problemasTeam[i][j] == 1)
            if solved:
                problemasHtml += f'<td class="problemTeam">{_globo_img_html(globos_dir, j)}</td>'
            else:
                problemasHtml += '<td>-</td>'

        pos_display = r.get("pos", i)
        country = r.get("country", "-") or "-"
        flag_html = (
            f'<img src="file:///app/flags/{country.lower()}.svg" class="flag">'
            if country != "-" else ""
        )
        rows_html += f"""
    <tr {style}>
        <td class="numequipo">{pos_display}</td>
        <td class="team-col">{flag_html}<span>{r['userfullname']}</span></td>
        {problemasHtml}
        <td class="puntos">{r['problemas_resueltos']} ({r['points']})</td>
    </tr>"""

    return f"""<html>
<head><style>{RANKING_CSS}</style></head>
<body>
<div class="cabecera">
    <img src="file:///app/logorpc/rpc.png" class="logorpc">
    <h2>{titulo}</h2>
</div>
<table>
<tr><th>#</th><th>Equipo</th>{headers}<th>Total</th></tr>
{rows_html}
</table>
</body>
</html>"""


def _screenshot_html(html_content, output_path=None):
    """Renders HTML to JPEG via weasyprint (no browser needed)."""
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
            crop_y = min(y + 40, h)
            break
    img = img.crop((0, 0, w, crop_y))

    if output_path:
        img.save(output_path, 'JPEG', quality=85)
        return None
    else:
        buf = BytesIO()
        img.save(buf, 'JPEG', quality=85)
        return buf.getvalue()


def generate_ranking(year, contest):
    file_key = _file_key(year, contest)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        response = requests.get(_bd_url(BD_SERVICE_URL, "/api/ranking", year, contest), timeout=10)
        if response.status_code != 200:
            raise Exception(f"Error obteniendo ranking: {response.text}")
        data = response.json()
        if not data.get("success"):
            raise Exception(f"Error en la respuesta: {data.get('error')}")
        rows = data["rows"]
        cantidadProblemas = data["cantidadProblemas"]
    except Exception as e:
        raise Exception(f"Error comunicación con servicio bd: {e}")

    try:
        response = requests.get(_bd_url(BD_SERVICE_URL, "/api/teams/ac", year, contest), timeout=10)
        if response.status_code != 200:
            raise Exception(f"Error obteniendo AC runs: {response.text}")
        ac_data = response.json()
        if not ac_data.get("success"):
            raise Exception(f"Error en la respuesta AC: {ac_data.get('error')}")
        teamsAC = [(r["usernumber"], r["runproblem"]) for r in ac_data["rows"]]
    except Exception as e:
        raise Exception(f"Error comunicación con servicio bd (AC): {e}")

    teams = [row["usernumber"] for row in rows]
    teamsIndex = {team: i for i, team in enumerate(teams)}
    problemasTeam = [[0] * cantidadProblemas for _ in range(10)]

    for team, problem in teamsAC:
        if team in teamsIndex:
            i = teamsIndex[team]
            j = problem - 1
            if 0 <= j < cantidadProblemas:
                problemasTeam[i][j] = 1

    globos_dir = _ensure_globos(cantidadProblemas, year=year, contest=contest)
    html = _ranking_html(rows, cantidadProblemas, problemasTeam, globos_dir=globos_dir)
    html_path = os.path.join(OUTPUT_DIR, f"ranking_{file_key}.html")
    jpg_path = os.path.join(OUTPUT_DIR, f"ranking_{file_key}.jpg")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    _screenshot_html(html, jpg_path)
    return file_key, jpg_path


@app.route('/generate', methods=['POST'])
def generate():
    year, contest = _contest_params()
    try:
        file_key, jpg_path = generate_ranking(year, contest)
        return jsonify({"status": "success", "message": "Tabla generated successfully", "file": f"ranking_{file_key}.jpg", "path": jpg_path}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[error] /generate fallo: {e}", flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ranking.jpg', methods=['GET'])
def get_image():
    year, contest = _contest_params()
    file_key = _file_key(year, contest)
    path = os.path.join(OUTPUT_DIR, f"ranking_{file_key}.jpg")
    try:
        return send_file(path, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 404


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5002)))
