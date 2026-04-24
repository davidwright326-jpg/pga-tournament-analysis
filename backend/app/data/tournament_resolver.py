"""Resolves the current or next upcoming tournament from a schedule."""
from datetime import date
from typing import Any, Optional


def resolve_current_tournament(
    current_date: date, schedule: list[Any]
) -> Optional[Any]:
    """
    Returns the tournament whose date range contains current_date,
    or the next upcoming tournament if none is active.
    Returns None if schedule is empty or all tournaments are in the past.

    Each tournament object must have ``start_date`` and ``end_date``
    attributes (``datetime.date``).

    Edge cases handled:
    - Empty schedule → None
    - No active tournament (schedule gap) → next upcoming tournament
    - Off-season / all tournaments in the past → None
    """
    if not schedule:
        return None

    # Sort by start_date to ensure deterministic resolution
    sorted_schedule = sorted(schedule, key=lambda t: t.start_date)

    # Check for active tournament
    for t in sorted_schedule:
        if t.start_date <= current_date <= t.end_date:
            return t

    # No active tournament — find next upcoming
    upcoming = [t for t in sorted_schedule if t.start_date > current_date]
    if upcoming:
        return upcoming[0]

    # All tournaments in the past (off-season)
    return None
