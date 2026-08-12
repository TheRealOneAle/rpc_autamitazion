from django.conf import settings


def rpc_context(request):
    """Expone en los templates el contexto base (p. ej. /rpc/publisher) para que
    el HTML/JS no asuma que la app vive en la raiz del dominio."""
    return {'CONTEXT_PATH': settings.FORCE_SCRIPT_NAME}
