"""Property-based tests for recency weighting."""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.analysis.scoring import apply_recency_weight


@given(
    stat_value=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
    weeks_ago=st.integers(min_value=0, max_value=200),
    k=st.integers(min_value=1, max_value=100),
    half_life=st.integers(min_value=1, max_value=52),
)
@settings(max_examples=200, deadline=5000)
def test_p6_recency_weight_monotonicity(stat_value, weeks_ago, k, half_life):
    """
    P6: Recency weight must be monotonically decreasing with time.
    A stat from week N must receive a higher weight than from week N+K.
    **Validates: Requirements 3.4**
    """
    weight_earlier = apply_recency_weight(stat_value, weeks_ago, half_life)
    weight_later = apply_recency_weight(stat_value, weeks_ago + k, half_life)

    assert weight_earlier > weight_later, (
        f"Monotonicity violated: weight at {weeks_ago} weeks ({weight_earlier}) "
        f"<= weight at {weeks_ago + k} weeks ({weight_later})"
    )
