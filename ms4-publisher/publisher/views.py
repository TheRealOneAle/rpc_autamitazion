import json
import logging
import requests as http_requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    SocialToken, SystemConfig, UserConfig, PublicationLog,
    CoachSubscription, FirstSolutionEvent,
)
from .serializers import (
    SocialTokenSerializer, SocialTokenWriteSerializer, UserConfigSerializer,
    PublicationLogSerializer, CoachSubscriptionSerializer, FirstSolutionEventSerializer,
)

log = logging.getLogger(__name__)

USER_CONFIG_DEFAULTS = {
    'proceso_activo': 'true',
    'publication_text': '',
    'competition_name': '',
    'boca_year': '',
    'boca_contest': '',
    'activated_by': '',
    'top_n_size': '10',
    'active_rankings': '["LATAM"]',
    'fs_auto_publish': 'true',
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
    """Hace proxy de la imagen de ranking generada por MS2 para el contest del usuario, soportando país y top_n."""
    from .orchestrator import _bd_url
    ms2_url = _get_user_config(request.user, 'ms2_url') or settings.MS2_URL
    year, contest = _user_contest(request.user)

    country = request.GET.get('country', '')
    top_n_param = request.GET.get('top_n', '')
    top_n = int(top_n_param) if top_n_param.isdigit() else 10

    try:
        url = _bd_url(ms2_url, "/ranking.jpg", year, contest, country=country, top_n=top_n)
        r = http_requests.get(url, timeout=12)
        r.raise_for_status()
        return HttpResponse(r.content, content_type="image/jpeg")
    except Exception as e:
        return HttpResponse(status=503, reason=str(e))


@login_required
def competition_stats(request):
    """Proxy de /api/stats de MS1 para el contest del usuario."""
    from .orchestrator import _bd_url
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
        from .scheduler import get_schedule_info

        _ensure_user_defaults(request.user)
        schedule_info = get_schedule_info()

        last_log = PublicationLog.objects.filter(user=request.user).first()
        proceso_activo = _get_user_config(request.user, 'proceso_activo', 'true')
        top_n = _get_user_config(request.user, 'top_n_size', '10')
        active_rankings = _get_user_config(request.user, 'active_rankings', '["LATAM"]')
        fs_auto = _get_user_config(request.user, 'fs_auto_publish', 'true')

        return Response({
            "proceso_activo": proceso_activo == 'true',
            "top_n_size": int(top_n) if top_n.isdigit() else 10,
            "active_rankings": json.loads(active_rankings) if active_rankings.startswith('[') else ["LATAM"],
            "fs_auto_publish": fs_auto == 'true',
            "scheduler_running": schedule_info.get("scheduler_running", False),
            "is_scheduled": schedule_info.get("is_scheduled", False),
            "scheduled_start": schedule_info.get("scheduled_start"),
            "cutoff": schedule_info.get("cutoff"),
            "next_runs": schedule_info.get("next_runs", []),
            "last_log": PublicationLogSerializer(last_log).data if last_log else None,
        })


class CountriesListView(APIView):
    """Obtiene la lista de países presentes en la competencia actual."""
    def get(self, request):
        from .orchestrator import _bd_url
        ms1_url = _get_user_config(request.user, 'ms1_url') or settings.MS1_URL
        year, contest = _user_contest(request.user)
        try:
            r = http_requests.get(_bd_url(ms1_url, "/api/countries", year, contest), timeout=10)
            if r.status_code == 200:
                return Response(r.json())
            return Response({"success": False, "countries": []}, status=r.status_code)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class FirstSolutionsListView(APIView):
    """Obtiene las First Solutions de la competencia y el historial de publicaciones."""
    def get(self, request):
        from .orchestrator import _bd_url
        ms1_url = _get_user_config(request.user, 'ms1_url') or settings.MS1_URL
        year, contest = _user_contest(request.user)
        contest_key = f"{year}/{contest}"

        # 1. First solutions en vivo desde scraper
        live_solutions = []
        try:
            r = http_requests.get(_bd_url(ms1_url, "/api/first-solutions", year, contest), timeout=10)
            if r.status_code == 200:
                live_solutions = r.json().get("first_solutions", [])
        except Exception as e:
            log.warning(f"Error consultando first solutions en vivo: {e}")

        # 2. Eventos registrados en BD
        db_events = FirstSolutionEvent.objects.filter(contest_key=contest_key)
        db_map = {e.problem_letter: FirstSolutionEventSerializer(e).data for e in db_events}

        # Combinar
        merged = []
        for sol in live_solutions:
            let = sol.get("problem_letter", "")
            is_published = let in db_map and db_map[let].get("success") and db_map[let].get("post_id")
            merged.append({
                **sol,
                "is_published": bool(is_published),
                "post_id": db_map[let].get("post_id") if let in db_map else None,
                "published_at": db_map[let].get("published_at") if let in db_map else None,
            })

        return Response({
            "success": True,
            "contest": contest_key,
            "first_solutions": merged,
            "total_solved": len(merged),
            "total_published": len([m for m in merged if m.get("is_published")]),
        })


class PublishFirstSolutionTriggerView(APIView):
    """Dispara manualmente la publicación de un First Solution."""
    def post(self, request):
        from .orchestrator import publish_first_solution_event
        fs_data = request.data.get("fs_data")
        if not fs_data or not isinstance(fs_data, dict):
            return Response({"error": "fs_data es requerido como objeto"}, status=status.HTTP_400_BAD_REQUEST)

        ok, result = publish_first_solution_event(fs_data, user=request.user)
        if ok:
            return Response({"success": True, "post_id": result})
        return Response({"success": False, "error": result}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScheduleStartView(APIView):
    """Permite fijar la hora exacta de inicio de la publicación del scoreboard."""
    def get(self, request):
        from .scheduler import get_schedule_info
        return Response(get_schedule_info())

    def post(self, request):
        from .scheduler import schedule_publication, BOGOTA_TZ
        from datetime import datetime

        start_str = str(request.data.get('start_time', '')).strip()
        end_str = str(request.data.get('end_time', '')).strip()

        if not start_str:
            return Response({"error": "start_time es requerido (formato YYYY-MM-DDTHH:MM o HH:MM)"}, status=status.HTTP_400_BAD_REQUEST)

        now = datetime.now(BOGOTA_TZ)

        try:
            if 'T' in start_str or '-' in start_str:
                start_dt = datetime.fromisoformat(start_str)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=BOGOTA_TZ)
            else:
                parts = start_str.split(':')
                h, m = int(parts[0]), int(parts[1])
                start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if start_dt < now:
                    from datetime import timedelta
                    start_dt += timedelta(days=1)
        except Exception as e:
            return Response({"error": f"Formato de start_time inválido: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        end_dt = None
        if end_str:
            try:
                if 'T' in end_str or '-' in end_str:
                    end_dt = datetime.fromisoformat(end_str)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=BOGOTA_TZ)
                else:
                    parts = end_str.split(':')
                    h, m = int(parts[0]), int(parts[1])
                    end_dt = start_dt.replace(hour=h, minute=m, second=0, microsecond=0)
            except Exception as e:
                log.warning(f"Error parseando end_time: {e}")

        UserConfig.objects.update_or_create(user=request.user, key='proceso_activo', defaults={'value': 'true'})
        UserConfig.objects.update_or_create(user=request.user, key='scheduled_start_time', defaults={'value': start_dt.isoformat()})

        result = schedule_publication(start_datetime=start_dt, end_datetime=end_dt)
        return Response(result, status=status.HTTP_200_OK)

    def delete(self, request):
        from .scheduler import cancel_scheduled_start
        cancel_scheduled_start()
        UserConfig.objects.update_or_create(user=request.user, key='scheduled_start_time', defaults={'value': ''})
        return Response({"message": "Inicio programado cancelado exitosamente"})


class WhitelistView(APIView):
    def get(self, request):
        from .models import AllowedEmail
        from .serializers import AllowedEmailSerializer
        allowed_db = AllowedEmail.objects.all()
        allowed_env = getattr(settings, 'ALLOWED_EMAILS', [])
        return Response({
            "database_emails": AllowedEmailSerializer(allowed_db, many=True).data,
            "environment_emails": allowed_env,
        })

    def post(self, request):
        from .models import AllowedEmail
        from .serializers import AllowedEmailSerializer
        email = str(request.data.get('email', '')).strip().lower()
        if not email or '@' not in email:
            return Response({"error": "Correo electrónico no válido"}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = AllowedEmail.objects.get_or_create(
            email=email,
            defaults={'added_by': request.user, 'is_active': True},
        )
        if not created and not obj.is_active:
            obj.is_active = True
            obj.save()

        return Response(AllowedEmailSerializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WhitelistDeleteView(APIView):
    def delete(self, request, email_id):
        from .models import AllowedEmail
        try:
            item = AllowedEmail.objects.get(id=email_id)
            item.delete()
            return Response({"message": "Correo eliminado de la lista autorizada"})
        except AllowedEmail.DoesNotExist:
            return Response({"error": "Correo no encontrado"}, status=status.HTTP_404_NOT_FOUND)


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
        msg = f"Ciclo iniciado. Publicación final a las {cutoff.strftime('%H:%M')}"
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
    ALLOWED_KEYS = {
        'competition_name', 'publication_text', 'proceso_activo',
        'activated_by', 'scheduled_start_time', 'top_n_size',
        'active_rankings', 'fs_auto_publish',
    }

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
            val_str = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
            obj, _ = UserConfig.objects.update_or_create(
                user=request.user, key=key, defaults={"value": val_str}
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
        year = _get_user_config(request.user, 'boca_year', '')
        contest = _get_user_config(request.user, 'boca_contest', '')
        return Response({"year": year, "contest": contest})

    def put(self, request):
        year = str(request.data.get('year', '')).strip()
        contest = str(request.data.get('contest', '')).strip()
        if not year or not contest:
            return Response({"error": "year y contest son requeridos"}, status=status.HTTP_400_BAD_REQUEST)

        UserConfig.objects.update_or_create(user=request.user, key='boca_year', defaults={'value': year})
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
