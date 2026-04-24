"""Property-based tests for historical comparison delta correctness."""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.analysis.scoring import compute_comparison_delta, is_highlighted


@given(
    player_stat=st.floats(min_value=-10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    winner_avg=st.floats(min_value=-10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    threshold=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, deadline=5000)
def test_p7_historical_comparison_delta_correctness(player_stat, winner_avg, threshold):
    """
    P7: Delta must equal player_stat - winner_avg.
    Highlighting must be applied iff |delta| > threshold.
    **Validates: Requirements 6.2, 6.3**
    """
    delta = compute_comparison_delta(player_stat, winner_avg)
    expected_delta = player_stat - winner_avg

    assert abs(delta - expected_delta) < 1e-10, (
        f"Delta mismatch: computed={delta}, expected={expected_delta}"
    )

    highlighted = is_highlighted(delta, threshold)
    should_highlight = abs(delta) > threshold

    assert highlighted == should_highlight, (
        f"Highlight mismatch: delta={delta}, threshold={threshold}, "
        f"highlighted={highlighted}, should_highlight={should_highlight}"
    )
