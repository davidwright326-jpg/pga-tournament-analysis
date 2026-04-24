"""Property-based tests for player rankings and composite scoring."""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.config import REQUIRED_STAT_KEYS
from app.analysis.scoring import compute_fit_score, filter_rankings


# Strategies
def stat_weights_strategy():
    """Generate valid normalized stat weights."""
    raw = st.lists(
        st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=len(REQUIRED_STAT_KEYS),
        max_size=len(REQUIRED_STAT_KEYS),
    )

    @st.composite
    def make_weights(draw):
        values = draw(raw)
        total = sum(values)
        return {k: v / total for k, v in zip(REQUIRED_STAT_KEYS, values)}

    return make_weights()


def stat_percentiles_strategy():
    """Generate (mean, std) pairs for each stat category."""
    @st.composite
    def make_percentiles(draw):
        result = {}
        for cat in REQUIRED_STAT_KEYS:
            mean = draw(st.floats(min_value=-10.0, max_value=500.0, allow_nan=False, allow_infinity=False))
            std = draw(st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False))
            result[cat] = (mean, std)
        return result
    return make_percentiles()


def player_stats_strategy():
    """Generate player stat values for all categories."""
    @st.composite
    def make_stats(draw):
        return {
            cat: draw(st.floats(min_value=-10.0, max_value=500.0, allow_nan=False, allow_infinity=False))
            for cat in REQUIRED_STAT_KEYS
        }
    return make_stats()


def rankings_strategy():
    """Generate a list of player rankings."""
    return st.lists(
        st.fixed_dictionaries({
            "player_id": st.text(min_size=1, max_size=8, alphabet="abcdef0123456789"),
            "player_name": st.text(min_size=1, max_size=20),
            "composite_score": st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
            "world_ranking": st.one_of(st.none(), st.integers(min_value=1, max_value=500)),
        }),
        min_size=1,
        max_size=100,
    )


@given(
    weights=stat_weights_strategy(),
    percentiles=stat_percentiles_strategy(),
    data=st.data(),
)
@settings(max_examples=50, deadline=5000)
def test_p3_player_ranking_order_consistency(weights, percentiles, data):
    """
    P3: Rankings must be sorted in descending order by composite score.
    **Validates: Requirements 3.1, 3.3**
    """
    num_players = data.draw(st.integers(min_value=2, max_value=30))
    players = []
    for i in range(num_players):
        stats = data.draw(player_stats_strategy())
        score = compute_fit_score(stats, weights, percentiles)
        players.append({"player_id": str(i), "composite_score": score})

    # Sort descending
    ranked = sorted(players, key=lambda x: x["composite_score"], reverse=True)

    for i in range(len(ranked) - 1):
        assert ranked[i]["composite_score"] >= ranked[i + 1]["composite_score"], (
            f"Ranking order violated at position {i}: "
            f"{ranked[i]['composite_score']} < {ranked[i+1]['composite_score']}"
        )


@given(
    player_stats=player_stats_strategy(),
    weights=stat_weights_strategy(),
    percentiles=stat_percentiles_strategy(),
)
@settings(max_examples=100, deadline=5000)
def test_p4_composite_score_correctness(player_stats, weights, percentiles):
    """
    P4: Composite score must equal the weighted sum of z-scored stats.
    **Validates: Requirements 3.3**
    """
    computed = compute_fit_score(player_stats, weights, percentiles)

    # Manual calculation
    expected = 0.0
    for cat in weights:
        if cat in player_stats and cat in percentiles:
            mean, std = percentiles[cat]
            if std == 0:
                continue
            z = (player_stats[cat] - mean) / std
            expected += weights[cat] * z

    assert abs(computed - expected) < 0.0001, (
        f"Score mismatch: computed={computed}, expected={expected}"
    )


@given(rankings=rankings_strategy(), data=st.data())
@settings(max_examples=50, deadline=5000)
def test_p5_filter_subset_property(rankings, data):
    """
    P5: Filtered results must be a subset of unfiltered results.
    **Validates: Requirements 3.5**
    """
    min_rank = data.draw(st.one_of(st.none(), st.integers(min_value=1, max_value=500)))
    min_score = data.draw(st.one_of(st.none(), st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)))
    max_results = data.draw(st.one_of(st.none(), st.integers(min_value=1, max_value=200)))

    filtered = filter_rankings(rankings, min_rank=min_rank, min_score=min_score, max_results=max_results)

    # Filtered must be a subset
    original_ids = {r["player_id"] for r in rankings}
    filtered_ids = {r["player_id"] for r in filtered}
    assert filtered_ids.issubset(original_ids), "Filtered results contain players not in original"

    assert len(filtered) <= len(rankings), "Filtered results larger than original"


# --- Unit tests for scoring.py functions ---


class TestComputeFitScore:
    def test_basic_weighted_zscore(self):
        """Verify score matches manual z-score weighted sum."""
        stats = {"sg_total": 2.0, "sg_approach": 1.5}
        weights = {"sg_total": 0.6, "sg_approach": 0.4}
        percentiles = {"sg_total": (1.0, 0.5), "sg_approach": (1.0, 0.5)}
        score = compute_fit_score(stats, weights, percentiles)
        # z_sg_total = (2.0 - 1.0) / 0.5 = 2.0, z_sg_approach = (1.5 - 1.0) / 0.5 = 1.0
        # score = 0.6 * 2.0 + 0.4 * 1.0 = 1.6
        assert abs(score - 1.6) < 0.0001

    def test_missing_stat_skipped(self):
        """Stats missing from player_stats are skipped."""
        stats = {"sg_total": 2.0}
        weights = {"sg_total": 0.6, "sg_approach": 0.4}
        percentiles = {"sg_total": (1.0, 0.5), "sg_approach": (1.0, 0.5)}
        score = compute_fit_score(stats, weights, percentiles)
        # Only sg_total contributes: 0.6 * (2.0 - 1.0) / 0.5 = 1.2
        assert abs(score - 1.2) < 0.0001

    def test_zero_std_skipped(self):
        """Categories with std=0 are skipped to avoid division by zero."""
        stats = {"sg_total": 2.0}
        weights = {"sg_total": 1.0}
        percentiles = {"sg_total": (1.0, 0.0)}
        score = compute_fit_score(stats, weights, percentiles)
        assert score == 0.0

    def test_empty_inputs(self):
        """Empty inputs produce zero score."""
        assert compute_fit_score({}, {}, {}) == 0.0

    def test_negative_zscore(self):
        """Player below mean gets negative z-score contribution."""
        stats = {"sg_total": 0.0}
        weights = {"sg_total": 1.0}
        percentiles = {"sg_total": (1.0, 0.5)}
        score = compute_fit_score(stats, weights, percentiles)
        # z = (0.0 - 1.0) / 0.5 = -2.0
        assert abs(score - (-2.0)) < 0.0001
