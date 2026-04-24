"""Unit tests for player API endpoints."""
import pytest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base, Tournament, CourseStatWeight, TournamentResult,
    PlayerStat, PlayerFitScore,
)

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


from app.database import get_db
from app.main import app

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)

TOURNAMENT_ID = "R2026015"
SEASON = date.today().year


def _seed_tournament():
    db = TestSession()
    today = date.today()
    db.add(Tournament(
        id=TOURNAMENT_ID, name="The Masters", course_name="Augusta National",
        city="Augusta", state="GA", country="US", par=72, yardage=7510,
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=2),
        season=SEASON, purse=20000000.0,
    ))
    db.commit()
    db.close()


def _seed_weights():
    db = TestSession()
    db.add(CourseStatWeight(tournament_id=TOURNAMENT_ID, stat_category="sg_putting", weight=0.25, explanation="Putting key"))
    db.add(CourseStatWeight(tournament_id=TOURNAMENT_ID, stat_category="sg_approach", weight=0.20, explanation="Approach matters"))
    db.add(CourseStatWeight(tournament_id=TOURNAMENT_ID, stat_category="sg_total", weight=0.15, explanation="Overall SG"))
    db.commit()
    db.close()


def _seed_players(count=3):
    """Seed fit scores and stats for test players."""
    db = TestSession()
    now = datetime.utcnow()
    for i in range(count):
        pid = f"P{i:03d}"
        db.add(PlayerFitScore(
            tournament_id=TOURNAMENT_ID,
            player_id=pid,
            player_name=f"Player {i}",
            composite_score=round(2.0 - i * 0.5, 4),
            world_ranking=i + 1,
            fedex_ranking=i + 5,
            computed_at=now,
        ))
        db.add(PlayerStat(
            player_id=pid, player_name=f"Player {i}",
            season=SEASON, stat_category="sg_putting",
            stat_value=1.5 - i * 0.3, stat_rank=i + 1,
        ))
        db.add(PlayerStat(
            player_id=pid, player_name=f"Player {i}",
            season=SEASON, stat_category="sg_approach",
            stat_value=1.2 - i * 0.2, stat_rank=i + 2,
        ))
    db.commit()
    db.close()


# ── Rankings endpoint tests ──────────────────────────────────────────


class TestGetPlayerRankings:
    def test_returns_rankings_sorted_by_score(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(5)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tournament_id"] == TOURNAMENT_ID
        scores = [r["composite_score"] for r in data["rankings"]]
        assert scores == sorted(scores, reverse=True)

    def test_ranking_fields(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}")
        r = resp.json()["rankings"][0]
        for field in ["rank", "player_id", "player_name", "composite_score",
                       "world_ranking", "fedex_ranking", "stats", "stat_ranks"]:
            assert field in r

    def test_limit_param(self):
        _seed_tournament()
        _seed_players(5)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["rankings"]) == 2

    def test_min_rank_filter(self):
        _seed_tournament()
        _seed_players(5)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}&min_rank=2")
        assert resp.status_code == 200
        for r in resp.json()["rankings"]:
            assert r["world_ranking"] is not None
            assert r["world_ranking"] <= 2

    def test_min_score_filter(self):
        _seed_tournament()
        _seed_players(5)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}&min_score=1.0")
        assert resp.status_code == 200
        for r in resp.json()["rankings"]:
            assert r["composite_score"] >= 1.0

    def test_filter_stat(self):
        """filter_stat limits results to players who have that stat."""
        _seed_tournament()
        db = TestSession()
        now = datetime.utcnow()
        # Player A has sg_putting stat
        db.add(PlayerFitScore(tournament_id=TOURNAMENT_ID, player_id="PA",
               player_name="Player A", composite_score=2.0, computed_at=now))
        db.add(PlayerStat(player_id="PA", player_name="Player A",
               season=SEASON, stat_category="sg_putting", stat_value=1.5, stat_rank=1))
        # Player B has NO sg_putting stat
        db.add(PlayerFitScore(tournament_id=TOURNAMENT_ID, player_id="PB",
               player_name="Player B", composite_score=1.5, computed_at=now))
        db.add(PlayerStat(player_id="PB", player_name="Player B",
               season=SEASON, stat_category="sg_approach", stat_value=1.0, stat_rank=2))
        db.commit()
        db.close()

        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}&filter_stat=sg_putting")
        assert resp.status_code == 200
        ids = [r["player_id"] for r in resp.json()["rankings"]]
        assert "PA" in ids
        assert "PB" not in ids

    def test_key_stats_in_response(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}")
        data = resp.json()
        assert "key_stats" in data
        assert len(data["key_stats"]) > 0
        # Should be sorted by weight descending
        weights = [ks["weight"] for ks in data["key_stats"]]
        assert weights == sorted(weights, reverse=True)

    def test_empty_tournament_returns_empty(self):
        _seed_tournament()
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["rankings"] == []
        assert resp.json()["total"] == 0

    def test_player_stats_included(self):
        _seed_tournament()
        _seed_players(1)
        resp = client.get(f"/api/players/rankings?tournament_id={TOURNAMENT_ID}")
        r = resp.json()["rankings"][0]
        assert "sg_putting" in r["stats"]
        assert "sg_putting" in r["stat_ranks"]


# ── Profile endpoint tests ───────────────────────────────────────────


class TestGetPlayerProfile:
    def test_returns_profile(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/P000/profile?tournament_id={TOURNAMENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["player_id"] == "P000"
        assert data["player_name"] == "Player 0"
        assert data["tournament_id"] == TOURNAMENT_ID

    def test_profile_fields(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/P000/profile?tournament_id={TOURNAMENT_ID}")
        data = resp.json()
        for field in ["player_id", "player_name", "composite_score",
                       "world_ranking", "fedex_ranking", "comparison", "tournament_id"]:
            assert field in data

    def test_comparison_structure(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/P000/profile?tournament_id={TOURNAMENT_ID}")
        comp = resp.json()["comparison"]
        assert len(comp) > 0
        for entry in comp:
            for field in ["category", "display_name", "player_value",
                           "winner_avg", "delta", "highlighted", "weight"]:
                assert field in entry

    def test_comparison_sorted_by_weight(self):
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/P000/profile?tournament_id={TOURNAMENT_ID}")
        comp = resp.json()["comparison"]
        weights = [c["weight"] for c in comp]
        assert weights == sorted(weights, reverse=True)

    def test_404_for_unknown_player(self):
        _seed_tournament()
        resp = client.get(f"/api/players/UNKNOWN/profile?tournament_id={TOURNAMENT_ID}")
        assert resp.status_code == 404

    def test_delta_and_highlight(self):
        """When winner avg exists, delta and highlight should be computed."""
        _seed_tournament()
        _seed_weights()
        db = TestSession()
        now = datetime.utcnow()
        db.add(PlayerFitScore(tournament_id=TOURNAMENT_ID, player_id="PX",
               player_name="Test Player", composite_score=1.5, computed_at=now))
        db.add(PlayerStat(player_id="PX", player_name="Test Player",
               season=SEASON, stat_category="sg_putting", stat_value=2.0, stat_rank=1))
        # Add a past winner with stats
        db.add(TournamentResult(tournament_id=TOURNAMENT_ID, season=SEASON - 1,
               player_id="PW", player_name="Past Winner", position="1",
               total_score=270, par_relative_score=-18, rounds_played=4))
        db.add(PlayerStat(player_id="PW", player_name="Past Winner",
               season=SEASON - 1, stat_category="sg_putting", stat_value=1.0, stat_rank=5))
        db.commit()
        db.close()

        resp = client.get(f"/api/players/PX/profile?tournament_id={TOURNAMENT_ID}")
        assert resp.status_code == 200
        comp = resp.json()["comparison"]
        putting = next((c for c in comp if c["category"] == "sg_putting"), None)
        assert putting is not None
        assert putting["player_value"] == 2.0
        assert putting["winner_avg"] == 1.0
        assert putting["delta"] == 1.0
        # delta=1.0 > HIGHLIGHT_THRESHOLD=0.5 → highlighted
        assert putting["highlighted"] is True

    def test_no_winner_data_gives_null_delta(self):
        """When no historical winners exist, delta and winner_avg are null."""
        _seed_tournament()
        _seed_weights()
        _seed_players(1)
        resp = client.get(f"/api/players/P000/profile?tournament_id={TOURNAMENT_ID}")
        comp = resp.json()["comparison"]
        putting = next((c for c in comp if c["category"] == "sg_putting"), None)
        assert putting is not None
        assert putting["winner_avg"] is None
        assert putting["delta"] is None
        assert putting["highlighted"] is False
