"""Property-based and unit tests for tournament resolution."""
import pytest
from datetime import date, timedelta
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.data.tournament_resolver import resolve_current_tournament


class FakeTournament:
    """Lightweight tournament object for testing."""
    def __init__(self, tid: str, start: date, end: date):
        self.id = tid
        self.start_date = start
        self.end_date = end


# ── Unit tests for edge cases ──────────────────────────────────────


def test_empty_schedule_returns_none():
    """Empty schedule should return None."""
    assert resolve_current_tournament(date(2026, 6, 15), []) is None


def test_active_tournament_returned():
    """Date within a tournament's range returns that tournament."""
    t = FakeTournament("T1", date(2026, 6, 10), date(2026, 6, 14))
    result = resolve_current_tournament(date(2026, 6, 12), [t])
    assert result is not None
    assert result.id == "T1"


def test_active_on_start_date():
    """Date equal to start_date counts as active."""
    t = FakeTournament("T1", date(2026, 6, 10), date(2026, 6, 14))
    result = resolve_current_tournament(date(2026, 6, 10), [t])
    assert result is not None and result.id == "T1"


def test_active_on_end_date():
    """Date equal to end_date counts as active."""
    t = FakeTournament("T1", date(2026, 6, 10), date(2026, 6, 14))
    result = resolve_current_tournament(date(2026, 6, 14), [t])
    assert result is not None and result.id == "T1"


def test_next_upcoming_when_no_active():
    """When date falls in a gap, return the next upcoming tournament."""
    t1 = FakeTournament("T1", date(2026, 3, 1), date(2026, 3, 5))
    t2 = FakeTournament("T2", date(2026, 3, 20), date(2026, 3, 24))
    result = resolve_current_tournament(date(2026, 3, 10), [t1, t2])
    assert result is not None
    assert result.id == "T2"


def test_off_season_all_past_returns_none():
    """When all tournaments are in the past, return None."""
    t1 = FakeTournament("T1", date(2026, 1, 5), date(2026, 1, 9))
    t2 = FakeTournament("T2", date(2026, 2, 10), date(2026, 2, 14))
    result = resolve_current_tournament(date(2026, 12, 1), [t1, t2])
    assert result is None


def test_before_season_returns_first_tournament():
    """Date before any tournament returns the first upcoming one."""
    t1 = FakeTournament("T1", date(2026, 3, 1), date(2026, 3, 5))
    t2 = FakeTournament("T2", date(2026, 4, 1), date(2026, 4, 5))
    result = resolve_current_tournament(date(2026, 1, 1), [t2, t1])  # unsorted input
    assert result is not None
    assert result.id == "T1"


def test_unsorted_schedule_handled():
    """Schedule provided out of order is still resolved correctly."""
    t1 = FakeTournament("T1", date(2026, 5, 1), date(2026, 5, 5))
    t2 = FakeTournament("T2", date(2026, 3, 1), date(2026, 3, 5))
    t3 = FakeTournament("T3", date(2026, 7, 1), date(2026, 7, 5))
    result = resolve_current_tournament(date(2026, 5, 3), [t3, t1, t2])
    assert result is not None
    assert result.id == "T1"


def tournament_strategy():
    """Generate a list of non-overlapping tournaments."""
    @st.composite
    def make_schedule(draw):
        num = draw(st.integers(min_value=1, max_value=20))
        base = date(2026, 1, 1)
        tournaments = []
        current = base
        for i in range(num):
            gap = draw(st.integers(min_value=0, max_value=14))
            current = current + timedelta(days=gap)
            duration = draw(st.integers(min_value=3, max_value=5))
            end = current + timedelta(days=duration)
            tournaments.append(FakeTournament(f"T{i}", current, end))
            current = end + timedelta(days=1)
        return tournaments
    return make_schedule()


@given(schedule=tournament_strategy(), data=st.data())
@settings(max_examples=100, deadline=5000)
def test_p9_current_tournament_resolution(schedule, data):
    """
    P9: Resolver must return the active tournament or next upcoming.
    Result must be deterministic for any given date.
    **Validates: Requirements 1.2**
    """
    assume(len(schedule) > 0)

    # Pick a date within the range of the schedule (with some buffer)
    earliest = schedule[0].start_date - timedelta(days=30)
    latest = schedule[-1].end_date + timedelta(days=30)
    total_days = (latest - earliest).days
    assume(total_days > 0)

    day_offset = data.draw(st.integers(min_value=0, max_value=total_days))
    test_date = earliest + timedelta(days=day_offset)

    result = resolve_current_tournament(test_date, schedule)

    if result is not None:
        # Either the date falls within the tournament range
        is_active = result.start_date <= test_date <= result.end_date

        if not is_active:
            # Must be the next upcoming tournament
            assert result.start_date > test_date, (
                f"Result {result.id} is not active and not upcoming: "
                f"start={result.start_date}, date={test_date}"
            )
            # No other tournament should be active on this date
            active = [t for t in schedule if t.start_date <= test_date <= t.end_date]
            assert len(active) == 0, "An active tournament exists but resolver returned upcoming"

            # Should be the nearest upcoming
            upcoming = sorted(
                [t for t in schedule if t.start_date > test_date],
                key=lambda t: t.start_date,
            )
            if upcoming:
                assert result.id == upcoming[0].id, "Resolver didn't return nearest upcoming"

    # Determinism: calling again with same inputs gives same result
    result2 = resolve_current_tournament(test_date, schedule)
    if result is None:
        assert result2 is None
    else:
        assert result2 is not None and result.id == result2.id
