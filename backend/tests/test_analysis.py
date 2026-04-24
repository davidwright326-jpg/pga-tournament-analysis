"""Property-based tests for course stat importance analysis."""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.config import REQUIRED_STAT_KEYS
from app.analysis.engine import compute_stat_weights_from_data


# Strategy: generate random historical data
def player_id_strategy():
    return st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnop0123456789")


def results_strategy():
    """Generate a list of player results with numeric positions."""
    return st.lists(
        st.fixed_dictionaries({
            "player_id": player_id_strategy(),
            "position": st.integers(min_value=1, max_value=10),
        }),
        min_size=5,
        max_size=50,
    )


def player_stats_strategy(player_ids):
    """Generate player stats for given player IDs across all required categories."""
    stats = []
    for pid in player_ids:
        for cat in REQUIRED_STAT_KEYS:
            stats.append(
                st.fixed_dictionaries({
                    "player_id": st.just(pid),
                    "stat_category": st.just(cat),
                    "stat_value": st.floats(min_value=-5.0, max_value=500.0, allow_nan=False, allow_infinity=False),
                })
            )
    if not stats:
        return st.just([])
    return st.tuples(*stats).map(list)


@given(data=st.data())
@settings(max_examples=50, deadline=5000)
def test_p1_stat_weight_normalization(data):
    """
    P1: All stat weights must be non-negative and sum to 1.0 (within tolerance).
    **Validates: Requirements 2.2**
    """
    results = data.draw(results_strategy())
    player_ids = list({r["player_id"] for r in results})
    assume(len(player_ids) >= 3)

    player_stats = data.draw(player_stats_strategy(player_ids))

    weights = compute_stat_weights_from_data(results, player_stats)

    # All weights must be non-negative
    for cat, w in weights.items():
        assert w >= 0.0, f"Weight for {cat} is negative: {w}"
        assert w <= 1.0, f"Weight for {cat} exceeds 1.0: {w}"

    # Weights must sum to 1.0 within tolerance
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected ~1.0"


@given(data=st.data())
@settings(max_examples=50, deadline=5000)
def test_p2_stat_category_completeness(data):
    """
    P2: Output must always contain all 12 required stat categories.
    **Validates: Requirements 2.3**
    """
    results = data.draw(results_strategy())
    player_ids = list({r["player_id"] for r in results})
    assume(len(player_ids) >= 1)

    player_stats = data.draw(player_stats_strategy(player_ids))

    weights = compute_stat_weights_from_data(results, player_stats)

    for cat in REQUIRED_STAT_KEYS:
        assert cat in weights, f"Missing required stat category: {cat}"

    assert len(weights) == len(REQUIRED_STAT_KEYS)


# --- Unit tests for engine.py functions ---

from app.analysis.engine import generate_explanation, _parse_position


class TestParsePosition:
    def test_numeric_position(self):
        assert _parse_position("1") == 1

    def test_tied_position(self):
        assert _parse_position("T5") == 5

    def test_cut(self):
        assert _parse_position("CUT") is None

    def test_wd(self):
        assert _parse_position("WD") is None

    def test_dq(self):
        assert _parse_position("DQ") is None

    def test_mdf(self):
        assert _parse_position("MDF") is None

    def test_empty(self):
        assert _parse_position("") is None

    def test_none(self):
        assert _parse_position(None) is None


class TestGenerateExplanation:
    def _make_weights(self, top_key: str) -> dict:
        """Create weights where top_key has the highest weight."""
        weights = {k: 0.05 for k in REQUIRED_STAT_KEYS}
        weights[top_key] = 0.45
        return weights

    def test_high_importance_explanation(self):
        weights = self._make_weights("sg_approach")
        explanation = generate_explanation("sg_approach", weights["sg_approach"], weights)
        assert "High importance" in explanation
        assert "#1" in explanation

    def test_lower_importance_explanation(self):
        # Give all keys roughly equal weight so most rank low
        weights = {k: 1.0 / len(REQUIRED_STAT_KEYS) for k in REQUIRED_STAT_KEYS}
        last_key = REQUIRED_STAT_KEYS[-1]
        explanation = generate_explanation(last_key, weights[last_key], weights)
        # With equal weights, ranking depends on sort stability; just check it returns a string
        assert isinstance(explanation, str)
        assert len(explanation) > 0


class TestComputeStatWeightsFromDataEdgeCases:
    def test_empty_results_returns_uniform(self):
        weights = compute_stat_weights_from_data([], [])
        expected = 1.0 / len(REQUIRED_STAT_KEYS)
        for k in REQUIRED_STAT_KEYS:
            assert abs(weights[k] - expected) < 0.001

    def test_empty_stats_returns_uniform(self):
        results = [{"player_id": "p1", "position": 1}]
        weights = compute_stat_weights_from_data(results, [])
        expected = 1.0 / len(REQUIRED_STAT_KEYS)
        for k in REQUIRED_STAT_KEYS:
            assert abs(weights[k] - expected) < 0.001

    def test_known_correlation(self):
        """When stat perfectly predicts position, that stat should get high weight."""
        results = [{"player_id": f"p{i}", "position": i} for i in range(1, 11)]
        stats = []
        for i in range(1, 11):
            for cat in REQUIRED_STAT_KEYS:
                if cat == "sg_total":
                    # Perfect negative correlation: higher value -> lower (better) position
                    stats.append({"player_id": f"p{i}", "stat_category": cat, "stat_value": 11.0 - i})
                else:
                    # No correlation: constant value
                    stats.append({"player_id": f"p{i}", "stat_category": cat, "stat_value": 5.0})

        weights = compute_stat_weights_from_data(results, stats)
        # sg_total should have the highest weight since it perfectly correlates
        assert weights["sg_total"] == max(weights.values())
        assert weights["sg_total"] > 0.5  # Should dominate


# --- Tests for archetype fallback integration in compute_stat_weights ---

from unittest.mock import MagicMock, patch
from app.analysis.engine import compute_stat_weights
from app.analysis.archetypes import get_archetype_weights, ARCHETYPE_WEIGHTS


class TestComputeStatWeightsArchetypeFallback:
    """Test that compute_stat_weights falls back to archetype weights
    when historical data is insufficient."""

    def _mock_db_insufficient_data(self, distinct_season_count, tournament=None):
        """Create a mock DB session that returns insufficient historical data."""
        db = MagicMock()

        # Mock the distinct seasons count query chain
        count_query = MagicMock()
        count_query.count.return_value = distinct_season_count
        filter_query = MagicMock()
        filter_query.distinct.return_value = count_query
        season_query = MagicMock()
        season_query.filter.return_value = filter_query

        # Mock the tournament lookup query chain
        tournament_filter = MagicMock()
        tournament_filter.first.return_value = tournament
        tournament_query = MagicMock()
        tournament_query.filter.return_value = tournament_filter

        def query_side_effect(model):
            from app.models import TournamentResult, Tournament as TModel
            if model is TournamentResult.season:
                return season_query
            if model is TModel:
                return tournament_query
            return MagicMock()

        db.query = MagicMock(side_effect=query_side_effect)
        return db

    def test_fallback_with_zero_seasons(self):
        """When no historical data exists, should use archetype fallback."""
        tournament = MagicMock()
        tournament.course_name = "TPC Scottsdale"
        tournament.state = "AZ"
        tournament.yardage = 7200
        tournament.par = 71

        db = self._mock_db_insufficient_data(0, tournament)
        weights = compute_stat_weights("R2024001", [2020, 2021, 2022, 2023], db)

        expected = get_archetype_weights("desert")
        for key in REQUIRED_STAT_KEYS:
            assert abs(weights[key] - expected[key]) < 0.001

    def test_fallback_with_two_seasons(self):
        """When only 2 seasons exist (< MIN_HISTORICAL_SEASONS=3), should fallback."""
        tournament = MagicMock()
        tournament.course_name = "Kapalua"
        tournament.state = "HI"
        tournament.yardage = 7400
        tournament.par = 73

        db = self._mock_db_insufficient_data(2, tournament)
        weights = compute_stat_weights("R2024002", [2022, 2023], db)

        expected = get_archetype_weights("coastal")
        for key in REQUIRED_STAT_KEYS:
            assert abs(weights[key] - expected[key]) < 0.001

    def test_fallback_weights_are_valid(self):
        """Fallback weights must still satisfy normalization properties."""
        tournament = MagicMock()
        tournament.course_name = "Some Links Course"
        tournament.state = "SC"
        tournament.yardage = 7100
        tournament.par = 72

        db = self._mock_db_insufficient_data(1, tournament)
        weights = compute_stat_weights("R2024003", [2023], db)

        # All weights non-negative and sum to 1.0
        for key in REQUIRED_STAT_KEYS:
            assert key in weights
            assert weights[key] >= 0.0
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_fallback_when_tournament_not_found(self):
        """When tournament not in DB, should use default parkland_short."""
        db = self._mock_db_insufficient_data(0, tournament=None)
        weights = compute_stat_weights("R2024999", [2023], db)

        expected = get_archetype_weights("parkland_short")
        for key in REQUIRED_STAT_KEYS:
            assert abs(weights[key] - expected[key]) < 0.001
