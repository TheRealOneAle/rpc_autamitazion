import logging
import requests as http_requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import SocialToken, SystemConfig, UserConfig, PublicationLog, CoachSubscription
from .serializers import (
    SocialTokenSerializer, SocialTokenWriteSerializer, UserConfigSerializer,
    PublicationLogSerializer, CoachSubscriptionSerializer,
)

log = logging.getLogger(__name__)

USER_CONFIG_DEFAULTS = {
    'proceso_activo': 'true',
    'publication_text': '',
    'competition_name': '',
    'boca_year': '',
    'boca_contest': '',
    'activated_by': '',
}


def _get_user_config(user, key, default=""):
    try:
        return UserConfig.objects.get(user=user, key=key).value
    except UserConfig.DoesNotExist:
        return default


def _ensure_user_defaults(user):
    """Crea las UserConfig por defecto si no existen (primer acceso)."""
    for key, value in USER_CONFIG_DEFAULTS.items():
        UserConfig.objects.get_or_create(user=user, key=key, defaults={'value': value})


def _config_is_complete(user):
    required = ['competition_name', 'boca_year', 'boca_contest']
    saved = set(UserConfig.objects.filter(user=user, key__in=required).values_list('key', flat=True))
    if not saved.issuperset(required):
        return False
    if any(not _get_user_config(user, k).strip() for k in required):
        return False
    return SocialToken.objects.filter(user=user).exists()


def _user_contest(user):
    year = _get_user_config(user, 'boca_year', '').strip()
    contest = _get_user_config(user, 'boca_contest', '').strip()
    return year, contest


def dashboard(request):
    _ensure_user_defaults(request.user)
    if not _config_is_complete(request.user):
        return redirect('configuracion')
    return render(request, 'publisher/dashboard.html')


def configuracion(request):
    _ensure_user_defaults(request.user)
    return render(request, 'publisher/config.html')


@login_required
def preview_image(request):
    """Hace proxy de la imagen de ranking generada por MS2 para el contest del usuario."""
    from .orchestrator import _bd_url
    ms2_url = _get_user_config(request.user, 'ms2_url') or settings.MS2_URL
    year, contest = _user_contest(request.user)
    try:
        url = _bd_url(ms2_url, "/ranking.jpg", year, contest)
        r = http_requests.get(url, timeout=10)
        r.raise_for_status()
        return HttpResponse(r.content, content_type="image/jpeg")
    except Exception as e:
        return HttpResponse(status=503, reason=str(e))


@login_required
def competition_stats(request):
    """Proxy de /api/stats de MS1 para el contest del usuario."""
    from .orchestrator import _bd_url
    from django.http import JsonResponse
    ms1_url = _get_user_config(request.user, 'ms1_url') or settings.MS1_URL
    year, contest = _user_contest(request.user)
    try:
        r = http_requests.get(_bd_url(ms1_url, "/api/stats", year, contest), timeout=10)
        r.raise_for_status()
        return JsonResponse(r.json())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=503)


class StatusView(APIView):
    def get(self, request):
        from .scheduler import get_scheduler, get_cutoff

        _ensure_user_defaults(request.user)
        scheduler = get_scheduler()
        cutoff = get_cutoff()
        next_runs = []
        if scheduler and scheduler.running:
            for job_id, label in [('rpc_hourly_publication', 'cada hora'),
                                  ('rpc_final_publication', 'final')]:
                job = scheduler.get_job(job_id)
                if job and job.next_run_time:
                    next_runs.append({
                        "id": job_id,
                        "label": label,
                        "next_run": job.next_run_time.isoformat(),
                    })

        last_log = PublicationLog.objects.filter(user=request.user).first()
        proceso_activo = _get_user_config(request.user, 'proceso_activo', 'true')

        return Response({
            "proceso_activo": proceso_activo == 'true',
            "scheduler_running": scheduler.running if scheduler else False,
            "cutoff": cutoff.isoformat(),
            "next_runs": next_runs,
            "last_log": PublicationLogSerializer(last_log).data if last_log else None,
        })


class TriggerView(APIView):
    def post(self, request):
        from .scheduler import start_publication_cycle, get_cutoff
        from .orchestrator import _publish_for_user
        import threading

        UserConfig.objects.update_or_create(
            user=request.user, key='proceso_activo',
            defaults={'value': 'true'}
        )

        started = start_publication_cycle()
        t = threading.Thread(
            target=_publish_for_user,
            kwargs={"user": request.user, "force": True},
            daemon=True,
        )
        t.start()

        cutoff = get_cutoff()
        if started:
            msg = f"Ciclo iniciado. Publicación final programada para las {cutoff.strftime('%H:%M')}"
        else:
            msg = f"Scheduler ya corriendo. Publicación final a las {cutoff.strftime('%H:%M')}"

        return Response({"detail": msg, "cutoff": cutoff.isoformat()}, status=status.HTTP_202_ACCEPTED)


class LogsView(APIView):
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        status_filter = request.query_params.get('status')
        qs = PublicationLog.objects.filter(user=request.user)
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        logs = qs[:limit]
        return Response(PublicationLogSerializer(logs, many=True).data)


class ConfigView(APIView):
    ALLOWED_KEYS = {'competition_name', 'publication_text', 'proceso_activo', 'activated_by'}

    def get(self, request):
        _ensure_user_defaults(request.user)
        configs = UserConfig.objects.filter(user=request.user, key__in=self.ALLOWED_KEYS)
        return Response(UserConfigSerializer(configs, many=True).data)

    def put(self, request):
        _ensure_user_defaults(request.user)
        updated = []
        for key, value in request.data.items():
            if key not in self.ALLOWED_KEYS:
                return Response({"detail": f"Clave no permitida: {key}"}, status=status.HTTP_400_BAD_REQUEST)
            obj, _ = UserConfig.objects.update_or_create(
                user=request.user, key=key, defaults={"value": str(value)}
            )
            updated.append(UserConfigSerializer(obj).data)
        return Response(updated)


class TokenView(APIView):
    def get(self, request):
        token = SocialToken.objects.filter(user=request.user).order_by('-updated_at').first()
        if token:
            return Response({"configured": True, "page_id": token.page_id})
        return Response({"configured": False})

    def post(self, request):
        serializer = SocialTokenWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        SocialToken.objects.filter(user=request.user).delete()
        token = serializer.save(user=request.user)
        return Response(SocialTokenSerializer(token).data, status=status.HTTP_201_CREATED)


class BocaConfigView(APIView):
    def get(self, request):
        _ensure_user_defaults(request.user)
        year    = _get_user_config(request.user, 'boca_year', '')
        contest = _get_user_config(request.user, 'boca_contest', '')
        return Response({"year": year, "contest": contest})

    def put(self, request):
        year    = str(request.data.get('year', '')).strip()
        contest = str(request.data.get('contest', '')).strip()
        if not year or not contest:
            return Response({"error": "year y contest son requeridos"}, status=status.HTTP_400_BAD_REQUEST)

        UserConfig.objects.update_or_create(user=request.user, key='boca_year',    defaults={'value': year})
        UserConfig.objects.update_or_create(user=request.user, key='boca_contest', defaults={'value': str(int(contest)).zfill(2)})

        return Response({"year": year, "contest": str(int(contest)).zfill(2)})


class CoachSubscribeView(APIView):
    def post(self, request):
        serializer = CoachSubscriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        coach = serializer.save(user=request.user)
        return Response(CoachSubscriptionSerializer(coach).data, status=status.HTTP_201_CREATED)


class CoachListView(APIView):
    def get(self, request):
        coaches = CoachSubscription.objects.filter(active=True, user=request.user)
        return Response(CoachSubscriptionSerializer(coaches, many=True).data)


class CoachStatsView(APIView):
    def get(self, request, coach_id):
        try:
            coach = CoachSubscription.objects.get(id=coach_id, active=True, user=request.user)
        except CoachSubscription.DoesNotExist:
            return Response({"detail": "Coach no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        last_log = PublicationLog.objects.filter(user=request.user, status='SUCCESS').first()
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
