import logging
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    BOGOTA_TZ = ZoneInfo('America/Bogota')
except ImportError:
    BOGOTA_TZ = timezone(timedelta(hours=-5))

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler = None
_scheduled_info = {
    'is_scheduled': False,
    'scheduled_start': None,
    'cutoff': None,
}

_COL_OFFSET = -5
_END_HOUR = 18
_END_MINUTE = 15


def _get_now_bogota():
    return datetime.now(BOGOTA_TZ)


def _next_cutoff(base_dt=None):
    ref = base_dt or _get_now_bogota()
    cutoff = ref.replace(hour=_END_HOUR, minute=_END_MINUTE, second=0, microsecond=0)
    if ref >= cutoff:
        cutoff += timedelta(days=1)
    return cutoff


def _ensure_scheduler():
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(timezone='America/Bogota')
        _scheduler.start()
    return _scheduler


def _check_first_solutions_job():
    """Job periódico (cada 35s) que monitorea nuevos First Solutions y los publica inmediatamente."""
    from django.contrib.auth.models import User
    from .models import UserConfig, FirstSolutionEvent
    from .orchestrator import _get_config, _user_contest_params, publish_first_solution_event
    from django.conf import settings
    import requests

    ms1_url = _get_config("ms1_url") or settings.MS1_URL

    for user in User.objects.filter(is_active=True):
        try:
            proceso_activo = UserConfig.objects.filter(user=user, key='proceso_activo').first()
            if not proceso_activo or proceso_activo.value.lower() != 'true':
                continue

            fs_auto = UserConfig.objects.filter(user=user, key='fs_auto_publish').first()
            if fs_auto and fs_auto.value.lower() == 'false':
                continue

            year, contest = _user_contest_params(user)
            contest_key = f"{year}/{contest}"

            # Consultar First Solutions de boca-scraper
            url = f"{ms1_url}/api/first-solutions?contest={year}%2F{contest}"
            r = requests.get(url, timeout=12)
            if r.status_code != 200:
                continue

            data = r.json()
            if not data.get("success"):
                continue

            solutions = data.get("first_solutions", [])
            for fs in solutions:
                letter = fs.get("problem_letter", "").upper()
                if not letter:
                    continue

                # Chequear si ya fue publicado
                exists = FirstSolutionEvent.objects.filter(
                    contest_key=contest_key,
                    problem_letter=letter,
                    success=True,
                ).exists()

                if not exists:
                    log.info(f"[SENSOR FS] ¡Nuevo First Solution detectado para problema {letter} por {fs.get('team_name')}!")
                    print(f"[SENSOR FS] ¡Nuevo First Solution detectado para problema {letter} por {fs.get('team_name')}!")
                    publish_first_solution_event(fs, user=user)

        except Exception as e:
            log.debug(f"[SENSOR FS] Error en polling para {user.username}: {e}")


def start_publication_cycle(custom_cutoff=None):
    """Inicia el ciclo regular de publicaciones (cada hora en punto hasta el cutoff) y el sensor First Solution."""
    global _scheduler, _scheduled_info
    scheduler = _ensure_scheduler()

    cutoff = custom_cutoff or _next_cutoff()
    _scheduled_info['cutoff'] = cutoff.isoformat()
    _scheduled_info['is_scheduled'] = False
    _scheduled_info['scheduled_start'] = None

    from .orchestrator import orchestrate_all

    # 1. Publicación horaria de scoreboard
    scheduler.add_job(
        func=orchestrate_all,
        trigger='cron',
        minute=0,
        id='rpc_hourly_publication',
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
    )

    # 2. Sensor reactivo First Solution (polling cada 35s)
    scheduler.add_job(
        func=_check_first_solutions_job,
        trigger='interval',
        seconds=35,
        id='rpc_first_solutions_sensor',
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
    )

    # 3. Publicación final
    scheduler.add_job(
        func=_final_and_stop,
        trigger='date',
        run_date=cutoff,
        id='rpc_final_publication',
        replace_existing=True,
    )

    msg = f"Scheduler iniciado: publicación horaria + sensor First Solution (35s) + final a las {cutoff.strftime('%H:%M')}"
    log.info(msg)
    print(f"[SCHEDULER] {msg}")

    return True


def schedule_publication(start_datetime: datetime, end_datetime: datetime = None):
    """Programa el inicio de las publicaciones para una fecha/hora exacta futura."""
    global _scheduled_info
    scheduler = _ensure_scheduler()

    now = _get_now_bogota()
    if start_datetime.tzinfo is None:
        start_datetime = start_datetime.replace(tzinfo=BOGOTA_TZ)

    if start_datetime <= now:
        start_publication_cycle(custom_cutoff=end_datetime)
        from .orchestrator import orchestrate_all
        import threading
        threading.Thread(target=orchestrate_all, daemon=True).start()
        return {
            "status": "started_immediately",
            "message": "La hora programada es actual o pasada. El ciclo de publicación se inició de inmediato.",
        }

    cutoff = end_datetime or _next_cutoff(base_dt=start_datetime)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=BOGOTA_TZ)

    _scheduled_info = {
        'is_scheduled': True,
        'scheduled_start': start_datetime.isoformat(),
        'cutoff': cutoff.isoformat(),
    }

    if scheduler.get_job('rpc_hourly_publication'):
        scheduler.remove_job('rpc_hourly_publication')
    if scheduler.get_job('rpc_first_solutions_sensor'):
        scheduler.remove_job('rpc_first_solutions_sensor')
    if scheduler.get_job('rpc_final_publication'):
        scheduler.remove_job('rpc_final_publication')

    scheduler.add_job(
        func=_on_scheduled_start,
        trigger='date',
        run_date=start_datetime,
        args=[cutoff],
        id='rpc_scheduled_start',
        replace_existing=True,
        misfire_grace_time=300,
    )

    msg = f"Inicio programado para {start_datetime.strftime('%Y-%m-%d %H:%M')}. Publicación final a las {cutoff.strftime('%H:%M')}"
    log.info(msg)
    print(f"[SCHEDULER] {msg}")

    return {
        "status": "scheduled",
        "message": msg,
        "start_time": start_datetime.isoformat(),
        "cutoff": cutoff.isoformat(),
    }


def _on_scheduled_start(cutoff):
    """Callback invocado automáticamente cuando llega la hora programada."""
    global _scheduled_info
    log.info("[SCHEDULER] ¡Hora programada alcanzada! Iniciando primera publicación y ciclo...")
    print("[SCHEDULER] ¡Hora programada alcanzada! Iniciando primera publicación y ciclo...")

    from .orchestrator import orchestrate_all
    try:
        orchestrate_all()
    except Exception as e:
        log.exception(f"[SCHEDULER] Error en primera publicación programada: {e}")

    start_publication_cycle(custom_cutoff=cutoff)


def cancel_scheduled_start():
    """Cancela un inicio programado pendiente."""
    global _scheduler, _scheduled_info
    if _scheduler and _scheduler.get_job('rpc_scheduled_start'):
        _scheduler.remove_job('rpc_scheduled_start')
        log.info("[SCHEDULER] Inicio programado cancelado.")
        print("[SCHEDULER] Inicio programado cancelado.")

    _scheduled_info['is_scheduled'] = False
    _scheduled_info['scheduled_start'] = None
    return True


def _final_and_stop():
    from .orchestrator import orchestrate_all
    print("[SCHEDULER] Ejecutando publicación FINAL...")
    log.info("Ejecutando publicación FINAL...")
    orchestrate_all(final=True)
    stop_scheduler()
    msg = "Scheduler detenido después de publicación final."
    log.info(msg)
    print(f"[SCHEDULER] {msg}")


def stop_scheduler():
    global _scheduler, _scheduled_info
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler detenido.")
        print("[SCHEDULER] Scheduler detenido.")
    _scheduler = None
    _scheduled_info['is_scheduled'] = False
    _scheduled_info['scheduled_start'] = None


def get_scheduler():
    return _scheduler


def get_cutoff():
    return _next_cutoff()


def get_schedule_info():
    global _scheduler, _scheduled_info
    now = _get_now_bogota()
    cutoff_dt = _next_cutoff()

    next_runs = []
    if _scheduler and _scheduler.running:
        for job in _scheduler.get_jobs():
            if job.next_run_time:
                label = job.id
                if job.id == 'rpc_hourly_publication':
                    label = 'Publicación cada hora'
                elif job.id == 'rpc_first_solutions_sensor':
                    label = 'Sensor First Solution (35s)'
                elif job.id == 'rpc_final_publication':
                    label = 'Publicación final'
                elif job.id == 'rpc_scheduled_start':
                    label = 'Inicio programado'
                next_runs.append({
                    "id": job.id,
                    "label": label,
                    "next_run": job.next_run_time.isoformat(),
                })

    is_scheduled = False
    scheduled_start = None
    if _scheduler and _scheduler.get_job('rpc_scheduled_start'):
        job = _scheduler.get_job('rpc_scheduled_start')
        if job.next_run_time and job.next_run_time > now:
            is_scheduled = True
            scheduled_start = job.next_run_time.isoformat()

    return {
        "scheduler_running": _scheduler.running if _scheduler else False,
        "is_scheduled": is_scheduled,
        "scheduled_start": scheduled_start or _scheduled_info.get('scheduled_start'),
        "cutoff": _scheduled_info.get('cutoff') or cutoff_dt.isoformat(),
        "next_runs": next_runs,
    }
