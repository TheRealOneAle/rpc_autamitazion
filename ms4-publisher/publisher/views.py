import json
import logging
import requests as http_requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    SocialToken, SystemConfig, UserConfig, PublicationLog,
    CoachSubscription, FirstSolutionEvent, ExecutionLog,
)
from .serializers import (
    SocialTokenSerializer, SocialTokenWriteSerializer, UserConfigSerializer,
    PublicationLogSerializer, CoachSubscriptionSerializer, FirstSolutionEventSerializer,
    ExecutionLogSerializer,
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


def get_last_publication_info(user=None):
    """Devuelve la información de la última publicación realizada (si fue Top o First Solution, y de qué RPC)."""
    # 1. Buscar en ExecutionLog (los más recientes con SUCCESS)
    qs = ExecutionLog.objects.filter(level='SUCCESS', pub_type__in=['TOP', 'FIRST_SOLUTION'])
    if user and user.is_authenticated:
        qs = qs.filter(user=user)
    last_exec = qs.first()

    # 2. Buscar en FirstSolutionEvent
    fs_qs = FirstSolutionEvent.objects.filter(success=True).exclude(post_id__isnull=True).exclude(post_id='')
    if user and user.is_authenticated:
        fs_qs = fs_qs.filter(user=user)
    last_fs = fs_qs.order_by('-published_at').first()

    # 3. Buscar en PublicationLog
    pub_qs = PublicationLog.objects.filter(status='SUCCESS').exclude(post_id__isnull=True).exclude(post_id='')
    if user and user.is_authenticated:
        pub_qs = pub_qs.filter(user=user)
    last_pub = pub_qs.order_by('-executed_at').first()

    candidates = []

    if last_exec:
        clean_title = (
            last_exec.message
            .replace("🚀 Publicado con éxito: ", "")
            .replace("🎈 Publicado con éxito: ", "")
            .replace(" en Facebook.", "")
        )
        candidates.append({
            "type": last_exec.pub_type,
            "type_label": "First Solution" if last_exec.pub_type == "FIRST_SOLUTION" else "Top Ranking",
            "title": clean_title,
            "rpc_name": last_exec.rpc_name or "RPC",
            "contest_key": last_exec.contest_key,
            "timestamp": last_exec.created_at,
            "post_id": last_exec.post_id,
        })

    if last_fs:
        contest_parts = last_fs.contest_key.split('/')
        num = contest_parts[1] if len(contest_parts) > 1 else contest_parts[0]
        rpc_lbl = f"RPC {str(num).zfill(2)}"
        candidates.append({
            "type": "FIRST_SOLUTION",
            "type_label": "First Solution",
            "title": f"Problema {last_fs.problem_letter} por '{last_fs.team_name}'",
            "rpc_name": rpc_lbl,
            "contest_key": last_fs.contest_key,
            "timestamp": last_fs.published_at,
            "post_id": last_fs.post_id,
        })

    if last_pub:
        scope = (last_pub.competition_data or {}).get("scope", "LATAM")
        top_n = (last_pub.competition_data or {}).get("top_n", 10)
        rpc_lbl = (last_pub.competition_data or {}).get("rpc_name", "")
        if not rpc_lbl and user and user.is_authenticated:
            c_num = _get_user_config(user, 'boca_contest', '')
            if c_num and c_num.isdigit():
                rpc_lbl = f"RPC {str(int(c_num)).zfill(2)}"
        candidates.append({
            "type": "TOP",
            "type_label": "Top Ranking",
            "title": f"Top {top_n} {scope}",
            "rpc_name": rpc_lbl or "RPC",
            "contest_key": "",
            "timestamp": last_pub.executed_at,
            "post_id": last_pub.post_id,
        })

    if not candidates:
        return {
            "has_publication": False,
            "message": "Sin publicaciones registradas aún",
        }

    # Ordenar por timestamp descendente
    candidates.sort(key=lambda x: x["timestamp"], reverse=True)
    best = candidates[0]

    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        bogota_tz = ZoneInfo('America/Bogota')
    except ImportError:
        from datetime import timezone, timedelta
        bogota_tz = timezone(timedelta(hours=-5))

    ts_local = best["timestamp"].astimezone(bogota_tz)
    now = datetime.now(bogota_tz)
    diff = max((now - ts_local).total_seconds(), 0)

    if diff < 60:
        time_ago = "Hace unos segundos"
    elif diff < 3600:
        time_ago = f"Hace {int(diff // 60)} min"
    elif diff < 86400:
        time_ago = f"Hace {int(diff // 3600)} h"
    else:
        time_ago = f"Hace {int(diff // 86400)} d"

    return {
        "has_publication": True,
        "type": best["type"],
        "type_label": best["type_label"],
        "title": best["title"],
        "rpc_name": best["rpc_name"],
        "contest_key": best["contest_key"],
        "timestamp": best["timestamp"].isoformat(),
        "formatted_date": ts_local.strftime("%d/%m/%Y %H:%M"),
        "time_ago": time_ago,
        "post_id": best["post_id"],
        "summary": f"{best['type_label']} ({best['rpc_name']}): {best['title']}",
    }


@login_required
def preview_image(request):
    """Hace proxy de la imagen de ranking generada por MS2 para el contest del usuario, soportando país y top_n."""
    from .orchestrator import _bd_url
    ms2_url = _get_user_config(request.user, 'ms2_url') or settings.MS2_URL
    year, contest = _user_contest(request.user)

    country = request.GET.get('country', '')
    top_n_param = request.GET.get('top_n', '')
    top_n = int(top_n_param) if top_n_param.isdigit() else 10

    contest_num = str(int(contest)).zfill(2) if contest and contest.isdigit() else "01"
    rpc_name = f"RPC {contest_num}"
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        BOGOTA_TZ = ZoneInfo('America/Bogota')
    except ImportError:
        from datetime import timezone, timedelta
        BOGOTA_TZ = timezone(timedelta(hours=-5))
    datetime_str = datetime.now(BOGOTA_TZ).strftime("%d/%m/%Y %H:%M")

    try:
        url = _bd_url(ms2_url, "/ranking.jpg", year, contest, country=country, top_n=top_n, rpc_name=rpc_name, datetime_str=datetime_str)
        r = http_requests.get(url, timeout=35)
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
        r = http_requests.get(_bd_url(ms1_url, "/api/stats", year, contest), timeout=35)
        r.raise_for_status()
        return JsonResponse(r.json())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=503)


class StatusView(APIView):
    def get(self, request):
        from .scheduler import get_schedule_info

        _ensure_user_defaults(request.user)
        schedule_info = get_schedule_info()

        last_pub_info = get_last_publication_info(request.user)
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
            "last_publication": last_pub_info,
        })


class CountriesListView(APIView):
    """Obtiene la lista de países presentes en la competencia actual."""
    def get(self, request):
        from .orchestrator import _bd_url
        ms1_url = _get_user_config(request.user, 'ms1_url') or settings.MS1_URL
        year, contest = _user_contest(request.user)
        try:
            r = http_requests.get(_bd_url(ms1_url, "/api/countries", year, contest), timeout=35)
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
            r = http_requests.get(_bd_url(ms1_url, "/api/first-solutions", year, contest), timeout=35)
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
        from .scheduler import start_publication_cycle, get_cutoff, cancel_hourly_jobs, BOGOTA_TZ
        from .orchestrator import _publish_for_user
        from datetime import datetime
        import threading

        now = datetime.now(BOGOTA_TZ)
        is_outside_contest = (now.hour >= 18)

        if is_outside_contest:
            # Fuera de hora de competencia (después de las 6pm):
            # Solo se publica esta vez puntual, sin reactivar publicaciones periódicas cada hora
            cancel_hourly_jobs()
            t = threading.Thread(
                target=_publish_for_user,
                kwargs={"user": request.user, "force": True, "final": True},
                daemon=True,
            )
            t.start()
            msg = "Publicación única iniciada (fuera de hora de competencia: solo se publica esta vez, no se programan publicaciones periódicas cada hora)."
            return Response({"detail": msg, "single_run": True}, status=status.HTTP_202_ACCEPTED)

        # Dentro del horario de competencia (antes de las 6pm): ciclo regular
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
        limit = int(request.query_params.get('limit', 150))
        contest_filter = (request.query_params.get('contest') or '').strip()
        level_filter = (request.query_params.get('level') or '').strip().upper()
        category_filter = (request.query_params.get('category') or '').strip().upper()

        qs = ExecutionLog.objects.all()
        if request.user and request.user.is_authenticated:
            qs = qs.filter(Q(user=request.user) | Q(user__isnull=True))

        if contest_filter and contest_filter.lower() not in ('all', 'todos'):
            qs = qs.filter(contest_key=contest_filter)

        if level_filter and level_filter not in ('ALL', 'TODOS', ''):
            if level_filter == 'PUBLICATIONS':
                qs = qs.filter(level='SUCCESS', category__in=['PUBLICATION', 'FIRST_SOLUTION'])
            else:
                qs = qs.filter(level=level_filter)

        if category_filter and category_filter not in ('ALL', 'TODOS', ''):
            qs = qs.filter(category=category_filter)

        logs = list(qs[:limit])
        # Invertir para orden cronológico terminal: los más viejos arriba y los más nuevos abajo
        logs.reverse()

        # Si aún no hay registros en ExecutionLog, poblar a partir de PublicationLog y FirstSolutionEvent
        if not logs and not contest_filter and not level_filter:
            legacy_logs = []
            for pl in PublicationLog.objects.filter(user=request.user)[:20]:
                scope = (pl.competition_data or {}).get('scope', 'LATAM')
                legacy_logs.append({
                    "id": f"pl_{pl.id}",
                    "contest_key": "",
                    "rpc_name": "RPC",
                    "pub_type": "TOP",
                    "level": pl.status,
                    "category": "PUBLICATION",
                    "message": f"🚀 Publicado Top {scope}" if pl.status == "SUCCESS" else f"❌ {pl.error_message}",
                    "post_id": pl.post_id,
                    "details": pl.competition_data,
                    "created_at": pl.executed_at.isoformat(),
                })
            for fs in FirstSolutionEvent.objects.filter(user=request.user)[:20]:
                legacy_logs.append({
                    "id": f"fs_{fs.id}",
                    "contest_key": fs.contest_key,
                    "rpc_name": f"RPC {fs.contest_key.split('/')[-1]}",
                    "pub_type": "FIRST_SOLUTION",
                    "level": "SUCCESS" if fs.success else "ERROR",
                    "category": "FIRST_SOLUTION",
                    "message": f"🎈 First Solution Problema {fs.problem_letter} por {fs.team_name}",
                    "post_id": fs.post_id,
                    "details": None,
                    "created_at": fs.published_at.isoformat(),
                })
            legacy_logs.sort(key=lambda x: x["created_at"], reverse=False)
            serialized_logs = legacy_logs[-limit:] if len(legacy_logs) > limit else legacy_logs
        else:
            serialized_logs = ExecutionLogSerializer(logs, many=True).data

        # Obtener lista de contests disponibles
        db_contests = list(ExecutionLog.objects.exclude(contest_key='').values_list('contest_key', flat=True).distinct())
        fs_contests = list(FirstSolutionEvent.objects.exclude(contest_key='').values_list('contest_key', flat=True).distinct())
        
        current_year, current_contest = _user_contest(request.user)
        current_key = f"{current_year}/{str(int(current_contest)).zfill(2)}" if current_year and current_contest and current_contest.isdigit() else ""

        all_keys = set(db_contests + fs_contests)
        if current_key:
            all_keys.add(current_key)

        contests_list = []
        for ck in sorted(all_keys, reverse=True):
            parts = ck.split('/')
            c_num = parts[1] if len(parts) > 1 else parts[0]
            label = f"RPC {str(c_num).zfill(2)} ({parts[0]})" if len(parts) > 1 else f"RPC {c_num}"
            if ck == current_key:
                label += " ⭐ (Activo)"
            contests_list.append({"key": ck, "label": label, "is_current": ck == current_key})

        last_pub = get_last_publication_info(request.user)

        return Response({
            "success": True,
            "last_publication": last_pub,
            "current_contest": current_key,
            "contests": contests_list,
            "logs": serialized_logs,
        })


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

        if 'top_n_size' in request.data:
            import re
            new_top = str(request.data['top_n_size']).strip()
            if new_top.isdigit():
                pub_obj = UserConfig.objects.filter(user=request.user, key='publication_text').first()
                if pub_obj and pub_obj.value:
                    new_val = re.sub(r'\bTop\s+\d+\b', f'Top {new_top}', pub_obj.value, flags=re.IGNORECASE)
                    if new_val != pub_obj.value:
                        pub_obj.value = new_val
                        pub_obj.save()
                        updated.append(UserConfigSerializer(pub_obj).data)
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
