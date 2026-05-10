import logging
import requests

log = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class FacebookTokenExpiredError(Exception):
    pass


class FacebookRateLimitError(Exception):
    pass


def _get_token_and_page():
    from .models import SocialToken
    token_obj = SocialToken.objects.order_by('-updated_at').first()
    if not token_obj:
        raise ValueError("No hay token de Facebook en la base de datos")
    return token_obj.access_token, token_obj.page_id


def publish_photo(image_bytes: bytes, description: str) -> str:
    """Publica una imagen en la Fan Page de Facebook. Retorna el post_id."""
    access_token, page_id = _get_token_and_page()

    url = f"{GRAPH_API_BASE}/{page_id}/photos"
    try:
        response = requests.post(
            url,
            data={"message": description, "access_token": access_token},
            files={"source": ("ranking.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
    except requests.RequestException as e:
        raise ConnectionError(f"Error de red al publicar en Facebook: {e}") from e

    data = response.json()

    if not response.ok:
        error = data.get("error", {})
        code = error.get("code")
        if code == 190:
            raise FacebookTokenExpiredError(f"Token de Facebook expirado: {error.get('message')}")
        if code in (4, 17, 32, 341):
            raise FacebookRateLimitError(f"Límite de tasa de Facebook: {error.get('message')}")
        raise RuntimeError(f"Error de Facebook API [{code}]: {error.get('message', response.text)}")

    post_id = data.get("post_id") or data.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook no retornó post_id. Respuesta: {data}")

    log.info(f"Publicado en Facebook: post_id={post_id}")
    return post_id
