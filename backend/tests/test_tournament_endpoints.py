"""Unit tests for tournament API endpoints."""
import pytest
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base, Tournament, CourseStatWeight, TournamentResult, PlayerStat, EventPlayerStat,
)

# Use StaticPool to ensure the same in-memory DB connection is shared
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


# Must import AFTER defining override
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def _insert_tournament(start_offset=0, tid="R2026015", name="The Masters"):
    db = TestSession()
    today = date.today()
    db.add(Tournament(
        id=tid, name=name, course_name="Augusta National",
        city="Augusta", state="GA", country="US", par=72, yardage=7510,
        start_date=today + timedelta(days=start_offset),
        end_date=today + timedelta(days=start_offset + 3),
        season=today.year, purse=20000000.0,
    ))
    db.commit()
    db.close()


class TestGetCurrentTournament:
    def test_returns_active_tournament(self):
        _insert_tournament(start_offset=-1)
        resp = client.get("/api/tournament/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tournament"] is not None
        assert data["tournament"]["id"] == "R2026015"
        assert data["message"] is None

    def test_returns_next_upcoming(self):
        _insert_tournament(tid="R2026020", name="PGA Championship", start_offset=10)
        resp = client.get("/api/tournament/current")
        assert resp.status_code == 200
        assert resp.json()["tournament"]["id"] == "R2026020"

    def test_no_tournaments_returns_none(self):
        resp = client.get("/api/tournament/current")
        assert resp.status_code == 200
        assert resp.json()["tournament"] is None
        assert resp.json()["message"] is not None

    def test_all_past_returns_none(self):
        _insert_tournament(start_offset=-30)
        resp = client.get("/api/tournament/current")
        assert resp.status_code == 200
        assert resp.json()["tournament"] is None

    def test_serialization_fields(self):
        _insert_tournament(start_offset=-1)
        resp = client.get("/api/tournament/current")
        t = resp.json()["tournament"]
        for f in ["id", "name", "course_name", "city", "state", "country",
                   "par", "yardage", "start_date", "end_date", "season", "purse"]:
            assert f in t


class TestGetTournamentStats:
    def test_returns_stat_weights(self):
        _insert_tournament()
        db = TestSession()
        db.add(CourseStatWeight(tournament_id="R2026015", stat_category="sg_putting",
                                weight=0.15, explanation="Putting is key"))
        db.add(CourseStatWeight(tournament_id="R2026015", stat_category="sg_approach",
                                weight=0.20, explanation="Approach matters"))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stats"]) == 2
        assert data["stats"][0]["weight"] >= data["stats"][1]["weight"]

    def test_stat_fields(self):
        _insert_tournament()
        db = TestSession()
        db.add(CourseStatWeight(tournament_id="R2026015", stat_category="sg_total",
                                weight=0.25, explanation="SG matters"))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/stats")
        stat = resp.json()["stats"][0]
        assert stat["category"] == "sg_total"
        assert stat["display_name"] == "SG: Total"
        assert "weight" in stat and "explanation" in stat

    def test_404_when_no_weights(self):
        _insert_tournament()
        resp = client.get("/api/tournament/R2026015/stats")
        assert resp.status_code == 404

    def test_generates_explanation_when_missing(self):
        _insert_tournament()
        db = TestSession()
        db.add(CourseStatWeight(tournament_id="R2026015", stat_category="sg_putting",
                                weight=0.5, explanation=None))
        db.add(CourseStatWeight(tournament_id="R2026015", stat_category="sg_approach",
                                weight=0.5, explanation=None))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/stats")
        assert resp.status_code == 200
        for stat in resp.json()["stats"]:
            assert stat["explanation"]


class TestGetTournamentHistory:
    def test_returns_past_winners(self):
        _insert_tournament()
        db = TestSession()
        cy = date.today().year
        db.add(TournamentResult(tournament_id="R2026015", season=cy - 1,
               player_id="P001", player_name="Tiger Woods", position="1",
               total_score=270, par_relative_score=-18, rounds_played=4))
        db.add(TournamentResult(tournament_id="R2026015", season=cy - 2,
               player_id="P002", player_name="Rory McIlroy", position="1",
               total_score=272, par_relative_score=-16, rounds_played=4))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["history"]) == 2
        assert data["history"][0]["season"] > data["history"][1]["season"]

    def test_winner_fields(self):
        _insert_tournament()
        db = TestSession()
        cy = date.today().year
        db.add(TournamentResult(tournament_id="R2026015", season=cy - 1,
               player_id="P001", player_name="Tiger Woods", position="1",
               total_score=270, par_relative_score=-18, rounds_played=4))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/history")
        entry = resp.json()["history"][0]
        for f in ["season", "player_id", "player_name", "position",
                   "total_score", "par_relative_score", "stats", "stat_ranks"]:
            assert f in entry

    def test_empty_history(self):
        _insert_tournament()
        resp = client.get("/api/tournament/R2026015/history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    def test_excludes_current_year(self):
        _insert_tournament()
        db = TestSession()
        db.add(TournamentResult(tournament_id="R2026015", season=date.today().year,
               player_id="P001", player_name="Tiger Woods", position="1",
               total_score=270, par_relative_score=-18, rounds_played=4))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/history")
        assert resp.json()["history"] == []

    def test_limit_parameter(self):
        _insert_tournament()
        db = TestSession()
        cy = date.today().year
        for i in range(5):
            db.add(TournamentResult(tournament_id="R2026015", season=cy - (i + 1),
                   player_id=f"P{i:03d}", player_name=f"Player {i}", position="1",
                   total_score=270, par_relative_score=-18, rounds_played=4))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/history?limit=3")
        assert len(resp.json()["history"]) == 3

    def test_event_stats(self):
        _insert_tournament()
        db = TestSession()
        cy = date.today().year
        db.add(TournamentResult(tournament_id="R2026015", season=cy - 1,
               player_id="P001", player_name="Tiger Woods", position="1",
               total_score=270, par_relative_score=-18, rounds_played=4))
        db.add(EventPlayerStat(tournament_id="R2026015", season=cy - 1,
               player_id="P001", player_name="Tiger Woods",
               stat_category="sg_putting", stat_value=2.5, stat_rank=1))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/history")
        entry = resp.json()["history"][0]
        assert entry["stats"]["sg_putting"] == 2.5

    def test_fallback_to_season_stats(self):
        _insert_tournament()
        db = TestSession()
        cy = date.today().year
        db.add(TournamentResult(tournament_id="R2026015", season=cy - 1,
               player_id="P001", player_name="Tiger Woods", position="1",
               total_score=270, par_relative_score=-18, rounds_played=4))
        db.add(PlayerStat(player_id="P001", player_name="Tiger Woods",
               season=cy - 1, stat_category="sg_approach",
               stat_value=1.8, stat_rank=5))
        db.commit()
        db.close()
        resp = client.get("/api/tournament/R2026015/history")
        entry = resp.json()["history"][0]
        assert entry["stats"]["sg_approach"] == 1.8
