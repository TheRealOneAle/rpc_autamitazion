import json
import logging
import pika
from django.conf import settings

log = logging.getLogger(__name__)


def publish_ranking_event(competition_data: dict, post_id: str = None):
    """Publica evento ranking.published en RabbitMQ."""
    try:
        params = pika.ConnectionParameters(
            host=settings.RABBIT_HOST,
            credentials=pika.PlainCredentials(settings.RABBIT_USER, settings.RABBIT_PASS),
            connection_attempts=3,
            retry_delay=2,
        )
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(exchange=settings.RABBIT_EXCHANGE, exchange_type='topic', durable=True)

        payload = {
            "ranking": competition_data.get("teams", []),
            "total_teams": len(competition_data.get("teams", [])),
            "post_id": post_id,
        }
        ch.basic_publish(
            exchange=settings.RABBIT_EXCHANGE,
            routing_key=settings.RABBIT_ROUTING_KEY,
            body=json.dumps(payload),
            properties=pika.BasicProperties(content_type='application/json', delivery_mode=2),
        )
        conn.close()
        log.info(f"Evento '{settings.RABBIT_ROUTING_KEY}' publicado en RabbitMQ")
    except Exception as e:
        log.warning(f"No se pudo publicar en RabbitMQ: {e}")
