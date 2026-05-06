from flask import Flask, jsonify, send_file
import os
import requests
import time
import json
import pika
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

app = Flask(__name__)

# URL del servicio bd
BD_SERVICE_URL = os.environ.get("BD_SERVICE_URL", "http://bd:3001")

RABBIT_HOST = os.environ.get("RABBIT_HOST", "rabbitmq")
RABBIT_USER = os.environ.get("RABBIT_USER", "rpc")
RABBIT_PASS = os.environ.get("RABBIT_PASS", "rpc1234")
EXCHANGE = "rpc.events"
ROUTING_KEY = "ranking.generado"
COACH_SERVICE_URL = os.environ.get("COACH_SERVICE_URL", "http://coach-service:5003")

def publish_ranking_event(ranking_rows, cantidad_problemas):
    """Publica evento ranking.generado en RabbitMQ."""
    import traceback
    for attempt in range(3):
        try:
            params = pika.ConnectionParameters(
                host=RABBIT_HOST,
                credentials=pika.PlainCredentials(RABBIT_USER, RABBIT_PASS),
                heartbeat=30, blocked_connection_timeout=10,
                connection_attempts=3, retry_delay=2,
            )
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

def generate_ranking():
    # 🔹 Obtener ranking desde el servicio bd
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

    # 🔹 Obtener runs AC por equipo
    try:
        teams = [row["usernumber"] for row in rows]
        response = requests.get(f"{BD_SERVICE_URL}/api/teams/ac", timeout=10)
        if response.status_code != 200:
            raise Exception(f"Error obteniendo AC runs: {response.text}")

        ac_data = response.json()
        if not ac_data.get("success"):
            raise Exception(f"Error en la respuesta AC: {ac_data.get('error')}")

        teamsAC = [(r["usernumber"], r["runproblem"]) for r in ac_data["rows"]]
    except Exception as e:
        raise Exception(f"Error comunicación con servicio bd (AC): {e}")

    teamsIndex = {team: i for i, team in enumerate(teams)}

    problemasTeam = [
        [0 for _ in range(cantidadProblemas)]
        for _ in range(10)
    ]

    for team, problem in teamsAC:
        if team in teamsIndex:
            i = teamsIndex[team]
            j = problem - 1

            if 0 <= j < cantidadProblemas:
                problemasTeam[i][j] = 1

    headers = ""
    for i in range(cantidadProblemas):
        headers += f"<th>{chr(65 + i)}</th>"
    rows_html = ""
    for i, r in enumerate(rows):
        style = ""
        if i == 0:
            style = 'style="background-color:#FFF673;"'
        elif i == 1:
            style = 'style="background-color:#9FCDD6;"'
        elif i == 2:
            style = 'style="background-color:#80C491;"'
        problemasHtml = ""
        for j in range(cantidadProblemas):
            if problemasTeam[i][j] == 1:
                problemasHtml += f'<td class="problemTeam"><img src="file:///app/globosgenerados/{chr(65 + j)}.png" class="balloon"></td>'
            else:
                problemasHtml += '<td>-</td>'
        rows_html += f"""
    <tr {style}>
        <td class="numequipo">{i}</td>
        <td class="team-col">
            <img src="file:///app/flags/{r['country'].lower()}.svg" class="flag">
            <span>{r['userfullname']}</span>
        </td>
        {problemasHtml}
        <td class="puntos">{r['problemas_resueltos']} ({r['points']})</td>
    </tr>
    """
    html = f"""
    <html>
    <head>
    <style>
    body {{
        font-family: Arial, sans-serif;
        background-color: #f4f6f7;
    }}
    .cabecera {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
    }}
    .logorpc {{
        width: 100px;
    }}
    table {{
        border-collapse: collapse;
        margin: auto;
        width: 65%;
        background: white;
        border-radius: 10px;
        overflow: hidden;
    }}
    th {{
        background-color: #CF1F4A;
        color: white;
        padding: 12px;
    }}
    td {{
        vertical-align: middle
    }}
    .numequipo {{
        text-align: center;
    }}
    .puntos{{
        text-align: center;
    }}
    .problemTeam {{
        text-align: center;
    }}
    tr:nth-child(even) {{
        background-color: #f2f2f2;
    }}
    .balloon {{
        width: 28px;
    }}
    .flag {{
        width: 25px;
        height: 25px;
        border-radius: 50%;
        vertical-align: middle
    }}
    .team-col {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px;
    }}
    </style>
    </head>
    <body>
    <div class="cabecera">
        <img src="logorpc/rpc.png" class="logorpc">
        <h2>Top 10 Latinoamerica</h2>
    </div>
    <table>
    <tr>
        <th>#</th>
        <th>Equipo</th>
        {headers}
        <th>Total</th>
    </tr>
    {rows_html}
    </table>
    </body>
    </html>
    """

    with open("ranking.html", "w", encoding="utf-8") as f:
        f.write(html)

    # Generate image using Selenium
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1200, 800)  # Adjust size as needed
    driver.get("file:///" + os.path.abspath("ranking.html"))
    time.sleep(2)  # Allow page to fully load
    driver.save_screenshot("ranking.jpg")
    driver.quit()

    # Para el evento usamos el ranking completo (todos los equipos, sin LIMIT 10)
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
    app.run(host='0.0.0.0', port=5002)