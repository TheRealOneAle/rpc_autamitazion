from flask import Flask, jsonify, send_file, request
import os
import requests
import time
import json
import tempfile
import pika
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

app = Flask(__name__)

BD_SERVICE_URL = os.environ.get("BD_SERVICE_URL", "http://bd:3001")
GLOBOS_SERVICE_URL = os.environ.get('GLOBOS_SERVICE_URL', 'http://generarglobos:5000')

RABBIT_HOST = os.environ.get("RABBIT_HOST", "rabbitmq")
RABBIT_USER = os.environ.get("RABBIT_USER", "rpc")
RABBIT_PASS = os.environ.get("RABBIT_PASS", "rpc1234")
EXCHANGE = "rpc.events"
ROUTING_KEY = "ranking.generado"
COACH_SERVICE_URL = os.environ.get("COACH_SERVICE_URL", "http://coach-service:5003")

RANKING_CSS = """
body { font-family: Arial, sans-serif; background-color: #f4f6f7; }
.cabecera { display: flex; align-items: center; justify-content: center; gap: 15px; }
.logorpc { width: 100px; }
table { border-collapse: collapse; margin: auto; width: 65%; background: white; border-radius: 10px; overflow: hidden; }
th { background-color: #CF1F4A; color: white; padding: 12px; }
td { vertical-align: middle }
.numequipo { text-align: center; }
.puntos { text-align: center; }
.problemTeam { text-align: center; }
tr:nth-child(even) { background-color: #f2f2f2; }
.balloon { width: 28px; }
.flag { width: 25px; height: 25px; border-radius: 50%; vertical-align: middle }
.team-col { display: flex; align-items: center; gap: 10px; padding: 10px; }
"""


def _get_rabbit_params():
    url = os.environ.get('CLOUDAMQP_URL')
    if url:
        return pika.URLParameters(url)
    return pika.ConnectionParameters(
        host=RABBIT_HOST,
        credentials=pika.PlainCredentials(RABBIT_USER, RABBIT_PASS),
        heartbeat=30, blocked_connection_timeout=10,
        connection_attempts=3, retry_delay=2,
    )


def _ensure_globos(cantidadProblemas):
    """Downloads balloon images from GLOBOS_SERVICE_URL to /tmp/globosgenerados/.
    Falls back to /app/globosgenerados/ if HTTP fails."""
    tmp_dir = '/tmp/globosgenerados'
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        for i in range(cantidadProblemas):
            letter = chr(65 + i)
            dest = os.path.join(tmp_dir, f'{letter}.png')
            if not os.path.exists(dest):
                r = requests.get(f"{GLOBOS_SERVICE_URL}/globo/{letter}.png", timeout=10)
                r.raise_for_status()
                with open(dest, 'wb') as f:
                    f.write(r.content)
        return tmp_dir
    except Exception as e:
        print(f"[warn] no se pudo descargar globos de {GLOBOS_SERVICE_URL}: {e}", flush=True)
        return '/app/globosgenerados'


def publish_ranking_event(ranking_rows, cantidad_problemas):
    import traceback
    for attempt in range(3):
        try:
            params = _get_rabbit_params()
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            ch.queue_declare(queue="ranking_queue", durable=True)
            ch.queue_bind(exchange=EXCHANGE, queue="ranking_queue", routing_key=ROUTING_KEY)

            payload = {
                "ranking": [
                    {"userfullname": r["userfullname"], "country": r["country"],
                     "usernumber": r["usernumber"], "problemas_resueltos": r["problemas_resueltos"],
                     "points": float(r["points"]) if r["points"] is not None else 0}
                    for r in ranking_rows
                ],
                "cantidad_problemas": cantidad_problemas,
            }
            ch.basic_publish(
                exchange=EXCHANGE, routing_key=ROUTING_KEY,
                body=json.dumps(payload),
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            )
            conn.close()
            print(f"[event] publicado {ROUTING_KEY} con {len(payload['ranking'])} equipos", flush=True)
            return
        except Exception as e:
            print(f"[event] intento {attempt+1} fallido: {e}", flush=True)
            traceback.print_exc()
            if attempt < 2:
                import time as _t; _t.sleep(2)
    print("[event] no se pudo publicar el evento después de 3 intentos", flush=True)


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
                problemasHtml += (
                    f'<td class="problemTeam">'
                    f'<img src="file://{globos_dir}/{chr(65 + j)}.png" class="balloon">'
                    f'</td>'
                )
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
    """Renders HTML to JPEG via Selenium.
    If output_path is given, saves there and returns None.
    Otherwise saves to a temp file and returns the image bytes."""
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.html', delete=False, encoding='utf-8', dir='/tmp'
    ) as f:
        f.write(html_content)
        tmp_html = f.name

    use_temp_output = output_path is None
    if use_temp_output:
        tmp_jpg = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False, dir='/tmp')
        tmp_jpg.close()
        output_path = tmp_jpg.name

    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1200, 800)
    try:
        driver.get(f"file://{tmp_html}")
        time.sleep(2)
        driver.save_screenshot(output_path)
    finally:
        driver.quit()
        os.unlink(tmp_html)

    if use_temp_output:
        with open(output_path, 'rb') as f:
            data = f.read()
        os.unlink(output_path)
        return data
    return None


def generate_ranking():
    try:
        response = requests.get(f"{BD_SERVICE_URL}/api/ranking", timeout=10)
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
        response = requests.get(f"{BD_SERVICE_URL}/api/teams/ac", timeout=10)
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

    globos_dir = _ensure_globos(cantidadProblemas)
    html = _ranking_html(rows, cantidadProblemas, problemasTeam, globos_dir=globos_dir)
    with open("ranking.html", "w", encoding="utf-8") as f:
        f.write(html)
    _screenshot_html(html, "ranking.jpg")

    try:
        resp_full = requests.get(f"{BD_SERVICE_URL}/api/ranking/full", timeout=10)
        if resp_full.status_code == 200 and resp_full.json().get("success"):
            all_rows = resp_full.json()["rows"]
        else:
            all_rows = rows
    except Exception as e:
        print(f"[warn] no se pudo obtener ranking completo, usando top-10: {e}", flush=True)
        all_rows = rows

    publish_ranking_event(all_rows, cantidadProblemas)


@app.route('/generate', methods=['POST'])
def generate():
    try:
        generate_ranking()
        return jsonify({"status": "success", "message": "Tabla generated successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ranking-coach.jpg', methods=['POST'])
def get_coach_image():
    try:
        data = request.get_json()
        team_numbers = set(data.get('teams', []))
        nombre_coach = data.get('nombre_coach', 'Coach')

        if not team_numbers:
            return jsonify({"status": "error", "message": "no teams provided"}), 400

        resp_full = requests.get(f"{BD_SERVICE_URL}/api/ranking/full", timeout=10)
        resp_full.raise_for_status()
        all_rows = resp_full.json()["rows"]

        rows = []
        for i, r in enumerate(all_rows, start=1):
            if r["usernumber"] in team_numbers:
                rows.append({**r, "pos": i})

        resp_ranking = requests.get(f"{BD_SERVICE_URL}/api/ranking", timeout=10)
        resp_ranking.raise_for_status()
        cantidadProblemas = resp_ranking.json()["cantidadProblemas"]

        resp_ac = requests.get(f"{BD_SERVICE_URL}/api/teams/ac", timeout=10)
        resp_ac.raise_for_status()
        teamsAC = [
            (r["usernumber"], r["runproblem"])
            for r in resp_ac.json()["rows"]
            if r["usernumber"] in team_numbers
        ]

        team_list = [r["usernumber"] for r in rows]
        teamsIndex = {team: i for i, team in enumerate(team_list)}
        problemasTeam = [[0] * cantidadProblemas for _ in range(len(rows))]

        for team, problem in teamsAC:
            if team in teamsIndex:
                i = teamsIndex[team]
                j = problem - 1
                if 0 <= j < cantidadProblemas:
                    problemasTeam[i][j] = 1

        globos_dir = _ensure_globos(cantidadProblemas)
        html = _ranking_html(rows, cantidadProblemas, problemasTeam, f"Equipos de {nombre_coach}", globos_dir=globos_dir)
        img_bytes = _screenshot_html(html)

        return send_file(BytesIO(img_bytes), mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ranking.jpg', methods=['GET'])
def get_image():
    try:
        return send_file('ranking.jpg', mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 404


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5002)))
