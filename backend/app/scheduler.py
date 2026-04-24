"""APScheduler setup for weekly auto-refresh."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import REFRESH_DAY, REFRESH_HOUR, REFRESH_MINUTE, REFRESH_TIMEZONE

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _refresh_job():
    """Scheduled refresh job wrapper. Delegates to _run_refresh_sync which handles status tracking."""
    from app.routes.system import _run_refresh_sync, _refresh_status

    logger.info("Scheduled weekly refresh starting")
    try:
        _run_refresh_sync()
        logger.info("Scheduled weekly refresh completed successfully, status=%s",
                     _refresh_status["status"])
    except Exception as e:
        logger.error("Scheduled weekly refresh failed with unexpected error: %s", e, exc_info=True)
        _refresh_status["status"] = "error"
        _refresh_status["error"] = f"Scheduler job error: {e}"


def start_scheduler():
    """Start the weekly refresh scheduler."""
    trigger = CronTrigger(
        day_of_week=REFRESH_DAY,
        hour=REFRESH_HOUR,
        minute=REFRESH_MINUTE,
        timezone=REFRESH_TIMEZONE,
    )
    scheduler.add_job(_refresh_job, trigger, id="weekly_refresh", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started: refresh every %s at %02d:%02d %s",
                REFRESH_DAY, REFRESH_HOUR, REFRESH_MINUTE, REFRESH_TIMEZONE)


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
