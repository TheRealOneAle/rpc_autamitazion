import logging
import requests as http_requests
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import SocialToken, SystemConfig, PublicationLog, CoachSubscription
from .serializers import (
    SocialTokenSerializer, SocialTokenWriteSerializer, SystemConfigSerializer,
    PublicationLogSerializer, CoachSubscriptionSerializer,
)

log = logging.getLogger(__name__)


def _config_is_complete():
    required = ['competition_name', 'boca_year', 'boca_contest']
    saved = set(SystemConfig.objects.filter(key__in=required).values_list('key', flat=True))
    if not saved.issuperset(required):
        return False
    return SocialToken.objects.exists()


def dashboard(request):
    if not _config_is_complete():
        return redirect('configuracion')
    return render(request, 'publisher/dashboard.html')


def configuracion(request):
    return render(request, 'publisher/config.html')


def preview_image(request):
    """Hace proxy de la imagen de ranking generada por MS2."""
    from .orchestrator import _get_config
    ms2_url = _get_config("ms2_url") or settings.MS2_URL
    try:
        r = http_requests.get(f"{ms2_url}/ranking.jpg", timeout=10)
        r.raise_for_status()
        return HttpResponse(r.content, content_type="image/jpeg")
    except Exception as e:
        return HttpResponse(status=503, reason=str(e))


def competition_stats(request):
    """Proxy de /api/stats de MS1 para que el frontend pueda consultarlo."""
    from .orchestrator import _get_config
    from django.http import JsonResponse
    ms1_url = _get_config("ms1_url") or settings.MS1_URL
    try:
        r = http_requests.get(f"{ms1_url}/api/stats", timeout=10)
        r.raise_for_status()
        return JsonResponse(r.json())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=503)


class StatusView(APIView):
    def get(self, request):
        from .scheduler import get_scheduler
        scheduler = get_scheduler()
        next_run = None
        if scheduler and scheduler.running:
            job = scheduler.get_job('rpc_hourly_publication')
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()

        last_log = PublicationLog.objects.first()
        proceso_activo = SystemConfig.objects.filter(key='proceso_activo').values_list('value', flat=True).first()

        from .description_builder import _contest_finished
        contest_ended = _contest_finished()

        return Response({
            "proceso_activo": proceso_activo == 'true' and not contest_ended,
            "contest_ended": contest_ended,
            "scheduler_running": scheduler.running if scheduler else False,
            "next_run": next_run,
            "last_log": PublicationLogSerializer(last_log).data if last_log else None,
        })


class TriggerView(APIView):
    def post(self, request):
        from .orchestrator import orchestrate_publication
        import threading
        t = threading.Thread(target=orchestrate_publication, kwargs={"force": True}, daemon=True)
        t.start()
        return Response({"detail": "Ciclo iniciado en segundo plano"}, status=status.HTTP_202_ACCEPTED)


class LogsView(APIView):
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        status_filter = request.query_params.get('status')
        qs = PublicationLog.objects.all()
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        logs = qs[:limit]
        return Response(PublicationLogSerializer(logs, many=True).data)


class ConfigView(APIView):
    ALLOWED_KEYS = {'ms1_url', 'ms2_url', 'landing_page_url', 'competition_name', 'proceso_activo', 'activated_by'}

    def get(self, request):
        configs = SystemConfig.objects.filter(key__in=self.ALLOWED_KEYS)
        return Response(SystemConfigSerializer(configs, many=True).data)

    def put(self, request):
        updated = []
        for key, value in request.data.items():
            if key not in self.ALLOWED_KEYS:
                return Response({"detail": f"Clave no permitida: {key}"}, status=status.HTTP_400_BAD_REQUEST)
            obj, _ = SystemConfig.objects.update_or_create(key=key, defaults={"value": str(value)})
            updated.append(SystemConfigSerializer(obj).data)
        return Response(updated)


class TokenView(APIView):
    def get(self, request):
        token = SocialToken.objects.first()
        if token:
            return Response({"configured": True, "page_id": token.page_id})
        return Response({"configured": False})

    def post(self, request):
        serializer = SocialTokenWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        SocialToken.objects.all().delete()
        token = serializer.save()
        return Response(SocialTokenSerializer(token).data, status=status.HTTP_201_CREATED)


class BocaConfigView(APIView):
    def get(self, request):
        year    = SystemConfig.objects.filter(key='boca_year').values_list('value', flat=True).first() or '2025'
        contest = SystemConfig.objects.filter(key='boca_contest').values_list('value', flat=True).first() or '10'
        return Response({"year": year, "contest": contest})

    def put(self, request):
        year    = str(request.data.get('year', '')).strip()
        contest = str(request.data.get('contest', '')).strip()
        if not year or not contest:
            return Response({"error": "year y contest son requeridos"}, status=status.HTTP_400_BAD_REQUEST)

        SystemConfig.objects.update_or_create(key='boca_year',    defaults={'value': year})
        SystemConfig.objects.update_or_create(key='boca_contest', defaults={'value': contest})

        ms1_url = settings.MS1_URL
        try:
            http_requests.post(f"{ms1_url}/config", json={"year": year, "contest": contest}, timeout=10)
        except Exception as e:
            log.warning(f"No se pudo notificar a boca-scraper: {e}")

        return Response({"year": year, "contest": contest})


class CoachSubscribeView(APIView):
    def post(self, request):
        serializer = CoachSubscriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        coach = serializer.save()
        return Response(CoachSubscriptionSerializer(coach).data, status=status.HTTP_201_CREATED)


class CoachListView(APIView):
    def get(self, request):
        coaches = CoachSubscription.objects.filter(active=True)
        return Response(CoachSubscriptionSerializer(coaches, many=True).data)


class CoachStatsView(APIView):
    def get(self, request, coach_id):
        try:
            coach = CoachSubscription.objects.get(id=coach_id, active=True)
        except CoachSubscription.DoesNotExist:
            return Response({"detail": "Coach no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        last_log = PublicationLog.objects.filter(status='SUCCESS').first()
        teams_data = []
        if last_log and last_log.competition_data:
            all_teams = last_log.competition_data.get("teams", [])
            coach_team_names = {t.get("name", "").lower() for t in coach.teams} if coach.teams else set()
            for i, team in enumerate(all_teams, start=1):
                team_name = (team.get("userfullname") or team.get("name", "")).lower()
                if team_name in coach_team_names:
                    teams_data.append({**team, "position": i})

        return Response({
            "coach": CoachSubscriptionSerializer(coach).data,
            "teams_in_ranking": teams_data,
            "last_updated": last_log.executed_at.isoformat() if last_log else None,
        })
