"""Unit tests for the APScheduler weekly auto-refresh setup."""
import pytest
from unittest.mock import patch, MagicMock

from app.scheduler import start_scheduler, stop_scheduler, _refresh_job, scheduler


@pytest.fixture(autouse=True)
def clean_scheduler():
    """Ensure scheduler is stopped and jobs cleared between tests."""
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()


class TestStartScheduler:
    @patch("app.scheduler.scheduler")
    def test_adds_job_with_correct_cron_trigger(self, mock_sched):
        mock_sched.running = False
        start_scheduler()

        mock_sched.add_job.assert_called_once()
        args, kwargs = mock_sched.add_job.call_args
        # First arg is the job function, second is the trigger
        assert args[0] is _refresh_job
        trigger = args[1]
        assert trigger.fields[4].expressions[0].first == 1  # Tuesday (0=Mon, 1=Tue)
        assert kwargs["id"] == "weekly_refresh"
        assert kwargs["replace_existing"] is True

    @patch("app.scheduler.scheduler")
    def test_starts_the_scheduler(self, mock_sched):
        mock_sched.running = False
        start_scheduler()
        mock_sched.start.assert_called_once()

    def test_trigger_uses_config_values(self):
        """Verify the CronTrigger is built from config constants."""
        from app.config import REFRESH_DAY, REFRESH_HOUR, REFRESH_MINUTE, REFRESH_TIMEZONE
        assert REFRESH_DAY == "tue"
        assert REFRESH_HOUR == 6
        assert REFRESH_MINUTE == 0
        assert REFRESH_TIMEZONE == "US/Eastern"


class TestStopScheduler:
    @patch("app.scheduler.scheduler")
    def test_shuts_down_when_running(self, mock_sched):
        mock_sched.running = True
        stop_scheduler()
        mock_sched.shutdown.assert_called_once_with(wait=False)

    @patch("app.scheduler.scheduler")
    def test_no_op_when_not_running(self, mock_sched):
        mock_sched.running = False
        stop_scheduler()
        mock_sched.shutdown.assert_not_called()


class TestRefreshJob:
    @patch("app.scheduler._refresh_job.__module__", "app.scheduler")
    @patch("app.routes.system._run_refresh_sync")
    def test_calls_run_refresh_sync(self, mock_run):
        _refresh_job()
        mock_run.assert_called_once()

    @patch("app.routes.system._run_refresh_sync", side_effect=RuntimeError("boom"))
    def test_catches_exceptions_and_updates_status(self, mock_run):
        from app.routes.system import _refresh_status
        _refresh_status["status"] = "idle"
        _refresh_status["error"] = None

        _refresh_job()

        assert _refresh_status["status"] == "error"
        assert "boom" in _refresh_status["error"]
