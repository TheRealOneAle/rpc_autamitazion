import logging
from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    from .orchestrator import orchestrate_publication

    _scheduler = BackgroundScheduler(timezone='America/Bogota')
    _scheduler.add_job(
        func=orchestrate_publication,
        trigger='cron',
        minute=0,
        id='rpc_hourly_publication',
        replace_existing=True,
    )
    _scheduler.start()
    log.info("Scheduler iniciado: publicación cada hora en punto")


def get_scheduler():
    return _scheduler
