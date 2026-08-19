import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler = None

_COL_OFFSET = -5
_END_HOUR = 18
_END_MINUTE = 15


def _next_cutoff():
    now = datetime.now(timezone(timedelta(hours=_COL_OFFSET)))
    cutoff = now.replace(hour=_END_HOUR, minute=_END_MINUTE, second=0, microsecond=0)
    if now >= cutoff:
        cutoff += timedelta(days=1)
    return cutoff


def start_publication_cycle():
    global _scheduler
    if _scheduler and _scheduler.running:
        msg = "Scheduler ya está corriendo. Ignorando."
        log.info(msg)
        print(f"[SCHEDULER] {msg}")
        return False

    from .orchestrator import orchestrate_all

    cutoff = _next_cutoff()

    _scheduler = BackgroundScheduler(timezone='America/Bogota')
    _scheduler.add_job(
        func=orchestrate_all,
        trigger='cron',
        minute=0,
        id='rpc_hourly_publication',
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
    )
    _scheduler.add_job(
        func=_final_and_stop,
        trigger='date',
        run_date=cutoff,
        id='rpc_final_publication',
        replace_existing=True,
    )
    _scheduler.start()
    msg = f"Scheduler iniciado: publicación cada hora en punto + final a las {cutoff.strftime('%H:%M')}"
    log.info(msg)
    print(f"[SCHEDULER] {msg}")

    jobs = _scheduler.get_jobs()
    for job in jobs:
        print(f"[SCHEDULER]   Job '{job.id}' → próximo: {job.next_run_time}")

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
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler detenido.")
        print("[SCHEDULER] Scheduler detenido.")
    _scheduler = None


def get_scheduler():
    return _scheduler


def get_cutoff():
    return _next_cutoff()
