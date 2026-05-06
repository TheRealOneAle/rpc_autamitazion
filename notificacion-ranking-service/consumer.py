import os, json, time, smtplib, ssl, logging, requests, pika
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from jinja2 import Template

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("notificacion")

RABBIT_HOST = os.environ.get("RABBIT_HOST", "rabbitmq")
RABBIT_USER = os.environ.get("RABBIT_USER", "rpc")
RABBIT_PASS = os.environ.get("RABBIT_PASS", "rpc1234")
EXCHANGE = "rpc.events"
QUEUE_GENERAL = "ranking_queue"
QUEUE_COACH = "ranking_coach_queue"
ROUTING_GENERAL = "ranking.generado"
ROUTING_COACH = "ranking.coach.generado"

COACH_SERVICE_URL = os.environ.get("COACH_SERVICE_URL", "http://coach-service:5003")
TABLA_SERVICE_URL = os.environ.get("TABLA_SERVICE_URL", "http://generartabla:5002")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_ADDR = os.environ.get("FROM_ADDR", SMTP_USER)

EMAIL_TEMPLATE = Template("""
<html><body style="font-family:Arial,sans-serif">
<h2>Ranking RPC — Actualización</h2>
<p>Hola <strong>{{coach.nombre}} {{coach.apellido}}</strong>,</p>
<p>Se generó un nuevo ranking de la competencia. Adjuntamos la tabla general como imagen.</p>

<h3>Tus equipos en el ranking</h3>
{% if mis_equipos %}
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
<tr style="background:#CF1F4A;color:white">
  <th>Pos. global</th><th>Equipo</th><th>País</th><th>Resueltos</th><th>Puntos</th>
</tr>
{% for r in mis_equipos %}
<tr><td>{{r.pos}}</td><td>{{r.userfullname}}</td><td>{{r.country}}</td>
    <td>{{r.problemas_resueltos}}</td><td>{{r.points}}</td></tr>
{% endfor %}
</table>
{% else %}
<p><em>Tus equipos no aparecen en el top de este ranking.</em></p>
{% endif %}

<h3>Ranking general (top 10)</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
<tr style="background:#CF1F4A;color:white">
  <th>#</th><th>Equipo</th><th>País</th><th>Resueltos</th><th>Puntos</th>
</tr>
{% for r in ranking %}
<tr><td>{{loop.index}}</td><td>{{r.userfullname}}</td><td>{{r.country}}</td>
    <td>{{r.problemas_resueltos}}</td><td>{{r.points}}</td></tr>
{% endfor %}
</table>
<p style="margin-top:20px;color:#666;font-size:12px">RPC SocialStream — UFPS 2026</p>
</body></html>
""")

def fetch_coaches():
    r = requests.get(f"{COACH_SERVICE_URL}/coaches", timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_ranking_image():
    try:
        r = requests.get(f"{TABLA_SERVICE_URL}/ranking.jpg", timeout=10)
        if r.status_code == 200:
            return r.content
    except Exception as e:
        log.warning(f"no se pudo obtener imagen: {e}")
    return None

def filtrar_por_coach(ranking, coach):
    team_ids = {t["usernumber"] for t in coach.get("teams", [])}
    out = []
    for i, row in enumerate(ranking, start=1):
        if row["usernumber"] in team_ids:
            out.append({**row, "pos": i})
    return out

def enviar_email(coach, ranking, mis_equipos, imagen):
    if not SMTP_USER:
        log.info(f"[mock] email a {coach['email']} ({len(mis_equipos)} equipos suyos)")
        return
    msg = MIMEMultipart("related")
    msg["Subject"] = "Ranking RPC actualizado"
    msg["From"] = FROM_ADDR
    msg["To"] = coach["email"]
    html = EMAIL_TEMPLATE.render(coach=coach, ranking=ranking, mis_equipos=mis_equipos)
    msg.attach(MIMEText(html, "html"))
    if imagen:
        img = MIMEImage(imagen, _subtype="jpeg")
        img.add_header("Content-Disposition", "attachment", filename="ranking.jpg")
        msg.attach(img)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls(context=ctx)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    log.info(f"email enviado a {coach['email']}")

def publish_coach_events(ch, ranking, coaches):
    """RF3: publica evento por coach con su ranking filtrado."""
    for coach in coaches:
        mis = filtrar_por_coach(ranking, coach)
        body = {"coach_id": coach["id"], "email": coach["email"],
                "mis_equipos": mis, "total_general": len(ranking)}
        ch.basic_publish(
            exchange=EXCHANGE, routing_key=ROUTING_COACH,
            body=json.dumps(body),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    log.info(f"publicados {len(coaches)} eventos {ROUTING_COACH}")

def on_ranking_generado(ch, method, props, body):
    try:
        data = json.loads(body)
        ranking = data["ranking"]
        coaches = fetch_coaches()
        imagen = fetch_ranking_image()
        log.info(f"ranking.generado recibido: {len(ranking)} equipos, {len(coaches)} coaches")

        # RF3: emite evento por coach
        publish_coach_events(ch, ranking, coaches)

        # RF2: envía emails
        for coach in coaches:
            mis = filtrar_por_coach(ranking, coach)
            enviar_email(coach, ranking, mis, imagen)

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        log.exception(f"error procesando ranking.generado: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def on_coach_event(ch, method, props, body):
    """Consumer de la cola por-coach (RF3)."""
    try:
        data = json.loads(body)
        log.info(f"ranking.coach.generado coach={data.get('coach_id')} equipos={len(data.get('mis_equipos', []))}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        log.exception(f"error en coach event: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def setup_channel(ch):
    ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(queue=QUEUE_GENERAL, durable=True)
    ch.queue_declare(queue=QUEUE_COACH, durable=True)
    ch.queue_bind(exchange=EXCHANGE, queue=QUEUE_GENERAL, routing_key=ROUTING_GENERAL)
    ch.queue_bind(exchange=EXCHANGE, queue=QUEUE_COACH, routing_key=ROUTING_COACH)
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_GENERAL, on_message_callback=on_ranking_generado)
    ch.basic_consume(queue=QUEUE_COACH, on_message_callback=on_coach_event)

def main():
    while True:
        try:
            log.info(f"conectando a rabbitmq {RABBIT_HOST}...")
            params = pika.ConnectionParameters(
                host=RABBIT_HOST,
                credentials=pika.PlainCredentials(RABBIT_USER, RABBIT_PASS),
                heartbeat=30, blocked_connection_timeout=10,
            )
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            setup_channel(ch)
            log.info("esperando mensajes...")
            ch.start_consuming()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.ConnectionClosedByBroker) as e:
            log.warning(f"conexión perdida ({e}), reintentando en 5s")
            time.sleep(5)
        except KeyboardInterrupt:
            log.info("bye"); return
        except Exception as e:
            log.exception(f"error inesperado: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
