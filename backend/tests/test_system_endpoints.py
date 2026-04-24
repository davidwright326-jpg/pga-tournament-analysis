"""Unit tests for system API endpoints (POST /refresh, GET /status)."""
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.database import get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_refresh_status():
    """Reset the in-memory refresh status before each test."""
    from app.routes.system import _refresh_status
    _refresh_status["last_refresh"] = None
    _refresh_status["status"] = "idle"
    _refresh_status["error"] = None
    yield


client = TestClient(app)


class TestGetStatus:
    def test_returns_idle_status_initially(self):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["last_refresh"] is None
        assert data["error"] is None

    def test_returns_all_required_fields(self):
        resp = client.get("/api/status")
        data = resp.json()
        assert "status" in data
        assert "last_refresh" in data
        assert "error" in data

    def test_reflects_completed_status(self):
        from app.routes.system import _refresh_status
        _refresh_status["status"] = "completed"
        _refresh_status["last_refresh"] = "2025-01-15T10:30:00"
        _refresh_status["error"] = None

        resp = client.get("/api/status")
        data = resp.json()
        assert data["status"] == "completed"
        assert data["last_refresh"] == "2025-01-15T10:30:00"
        assert data["error"] is None

    def test_reflects_error_status(self):
        from app.routes.system import _refresh_status
        _refresh_status["status"] = "error"
        _refresh_status["error"] = "Connection timeout"

        resp = client.get("/api/status")
        data = resp.json()
        assert data["status"] == "error"
        assert data["error"] == "Connection timeout"


class TestPostRefresh:
    @patch("app.routes.system._run_refresh_sync")
    @patch("app.routes.system.threading.Thread")
    def test_starts_refresh_thread(self, mock_thread_cls, mock_run):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Refresh started"
        assert data["status"] == "running"
        mock_thread_cls.assert_called_once_with(
            target=mock_run, daemon=True
        )
        mock_thread.start.assert_called_once()

    def test_rejects_when_already_running(self):
        from app.routes.system import _refresh_status
        _refresh_status["status"] = "running"

        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Refresh already in progress"
        assert data["status"]["status"] == "running"

    @patch("app.routes.system._run_refresh_sync")
    @patch("app.routes.system.threading.Thread")
    def test_refresh_allowed_after_completion(self, mock_thread_cls, mock_run):
        from app.routes.system import _refresh_status
        _refresh_status["status"] = "completed"
        _refresh_status["last_refresh"] = "2025-01-15T10:30:00"

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Refresh started"

    @patch("app.routes.system._run_refresh_sync")
    @patch("app.routes.system.threading.Thread")
    def test_refresh_allowed_after_error(self, mock_thread_cls, mock_run):
        from app.routes.system import _refresh_status
        _refresh_status["status"] = "error"
        _refresh_status["error"] = "Previous failure"

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        resp = client.post("/api/refresh")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Refresh started"
