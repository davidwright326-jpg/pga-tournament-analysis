"""Composite fit score calculation and recency weighting."""
import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.config import REQUIRED_STAT_KEYS, RECENCY_HALF_LIFE_WEEKS
from app.models import PlayerStat, PlayerFitScore, Tournament, EventPlayerStat

logger = logging.getLogger(__name__)


def apply_recency_weight(
    stat_value: float, weeks_ago: int, half_life: int = RECENCY_HALF_LIFE_WEEKS
) -> float:
    """
    Apply exponential decay recency weighting.
    Weight = stat_value * 2^(-weeks_ago / half_life)
    
    Args:
        stat_value: The raw stat value
        weeks_ago: How many weeks ago the stat was recorded
        half_life: Number of weeks for the weight to halve (default 12)
    
    Returns:
        Recency-weighted stat value
    """
    if weeks_ago < 0:
        raise ValueError("weeks_ago must be non-negative")
    if half_life <= 0:
        raise ValueError("half_life must be positive")
    weight = 2.0 ** (-weeks_ago / half_life)
    return stat_value * weight


def compute_fit_score(
    player_stats: dict[str, float],
    stat_weights: dict[str, float],
    stat_percentiles: dict[str, tuple[float, float]],
) -> float:
    """
    Compute composite fit score using z-score normalization and weighted sum.
    
    Args:
        player_stats: dict mapping stat_category -> player's stat value
        stat_weights: dict mapping stat_category -> importance weight (0-1, sum to 1)
        stat_percentiles: dict mapping stat_category -> (mean, std) for z-score calc
    
    Returns:
        Composite fit score (higher = better fit)
    """
    score = 0.0
    for cat in stat_weights:
        if cat not in player_stats or cat not in stat_percentiles:
            continue
        mean, std = stat_percentiles[cat]
        if std == 0:
            continue
        z_score = (player_stats[cat] - mean) / std
        score += stat_weights[cat] * z_score
    return score


def compute_stat_percentiles(
    season: int, db: Session
) -> dict[str, tuple[float, float]]:
    """Compute mean and std for each stat category across all players in a season."""
    import pandas as pd

    stats = (
        db.query(PlayerStat)
        .filter(PlayerStat.season == season, PlayerStat.stat_value.isnot(None))
        .all()
    )

    if not stats:
        return {}

    df = pd.DataFrame([
        {"stat_category": s.stat_category, "stat_value": s.stat_value}
        for s in stats
    ])

    percentiles = {}
    for cat in REQUIRED_STAT_KEYS:
        cat_data = df[df["stat_category"] == cat]["stat_value"]
        if len(cat_data) > 1:
            percentiles[cat] = (cat_data.mean(), cat_data.std())
        elif len(cat_data) == 1:
            percentiles[cat] = (cat_data.mean(), 1.0)
        else:
            percentiles[cat] = (0.0, 1.0)

    return percentiles


def _get_tournament_start_date(tournament_id: str, db: Session) -> Optional[date]:
    """Look up the start date for a tournament."""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if tournament and tournament.start_date:
        return tournament.start_date
    return None


def _compute_weeks_between(from_date: date, to_date: date) -> int:
    """Compute the number of weeks between two dates (non-negative)."""
    delta = (to_date - from_date).days
    return max(0, delta // 7)


def apply_recency_to_player_stats(
    player_stats_map: dict[str, dict[str, float]],
    tournament_id: str,
    season: int,
    db: Session,
    half_life: int = RECENCY_HALF_LIFE_WEEKS,
) -> dict[str, dict[str, float]]:
    """
    Apply recency weighting to player stats.

    Uses event-level stats when available: for each player and stat category,
    computes a recency-weighted average across all events in the season.
    Falls back to unweighted season-level stats if no event data exists.

    Args:
        player_stats_map: dict mapping player_id -> {stat_category -> stat_value}
        tournament_id: target tournament to compute recency relative to
        season: the season to pull event stats from
        db: database session
        half_life: recency half-life in weeks

    Returns:
        dict mapping player_id -> {stat_category -> recency-weighted stat_value}
    """
    target_date = _get_tournament_start_date(tournament_id, db)
    if target_date is None:
        logger.warning("No start date for tournament %s; skipping recency weighting", tournament_id)
        return player_stats_map

    # Try event-level stats for finer recency granularity
    event_stats = (
        db.query(EventPlayerStat)
        .filter(
            EventPlayerStat.season == season,
            EventPlayerStat.stat_value.isnot(None),
        )
        .all()
    )

    if not event_stats:
        logger.info("No event-level stats available; skipping recency weighting")
        return player_stats_map

    # Build a cache of tournament start dates for events
    event_tournament_ids = list({es.tournament_id for es in event_stats})
    tournaments = (
        db.query(Tournament)
        .filter(Tournament.id.in_(event_tournament_ids))
        .all()
    )
    event_dates: dict[str, date] = {
        t.id: t.start_date for t in tournaments if t.start_date
    }

    # Group event stats by player and category
    # For each (player, category), compute weighted average across events
    weighted_map: dict[str, dict[str, float]] = {}
    for player_id in player_stats_map:
        weighted_map[player_id] = {}

    player_event_data: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for es in event_stats:
        if es.player_id not in player_stats_map:
            continue
        event_date = event_dates.get(es.tournament_id)
        if event_date is None:
            continue
        weeks_ago = _compute_weeks_between(event_date, target_date)
        weight = 2.0 ** (-weeks_ago / half_life)

        if es.player_id not in player_event_data:
            player_event_data[es.player_id] = {}
        if es.stat_category not in player_event_data[es.player_id]:
            player_event_data[es.player_id][es.stat_category] = []
        player_event_data[es.player_id][es.stat_category].append(
            (es.stat_value, weight)
        )

    # Compute weighted averages
    for player_id, categories in player_event_data.items():
        for cat, values_weights in categories.items():
            total_weight = sum(w for _, w in values_weights)
            if total_weight > 0:
                weighted_val = sum(v * w for v, w in values_weights) / total_weight
                if player_id not in weighted_map:
                    weighted_map[player_id] = {}
                weighted_map[player_id][cat] = weighted_val

    # Merge: use recency-weighted values where available, fall back to season stats
    result: dict[str, dict[str, float]] = {}
    for player_id, season_stats in player_stats_map.items():
        result[player_id] = dict(season_stats)  # copy season stats as baseline
        if player_id in weighted_map:
            for cat, val in weighted_map[player_id].items():
                result[player_id][cat] = val

    logger.info(
        "Applied recency weighting for %d players using %d event stat records",
        len(player_event_data), len(event_stats),
    )
    return result


def compute_all_fit_scores(
    tournament_id: str,
    stat_weights: dict[str, float],
    season: int,
    db: Session,
) -> list[dict]:
    """
    Score all players and store results in the database.
    Applies recency weighting to player stats before scoring.
    Returns sorted list of player fit scores (descending).
    """
    from datetime import datetime
    from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

    percentiles = compute_stat_percentiles(season, db)

    # Get all players with stats for this season
    all_stats = (
        db.query(PlayerStat)
        .filter(PlayerStat.season == season, PlayerStat.stat_value.isnot(None))
        .all()
    )

    # Group stats by player
    player_stats_map: dict[str, dict] = {}
    player_names: dict[str, str] = {}
    for s in all_stats:
        if s.player_id not in player_stats_map:
            player_stats_map[s.player_id] = {}
            player_names[s.player_id] = s.player_name
        player_stats_map[s.player_id][s.stat_category] = s.stat_value

    # Apply recency weighting to player stats
    player_stats_map = apply_recency_to_player_stats(
        player_stats_map, tournament_id, season, db
    )

    # Compute scores
    scores = []
    for player_id, stats in player_stats_map.items():
        score = compute_fit_score(stats, stat_weights, percentiles)
        scores.append({
            "player_id": player_id,
            "player_name": player_names[player_id],
            "composite_score": round(score, 4),
            "stats": stats,
        })

    # Sort descending by composite score
    scores.sort(key=lambda x: x["composite_score"], reverse=True)

    # Store in database
    now = datetime.utcnow()
    for s in scores:
        stmt = sqlite_upsert(PlayerFitScore).values(
            tournament_id=tournament_id,
            player_id=s["player_id"],
            player_name=s["player_name"],
            composite_score=s["composite_score"],
            computed_at=now,
        ).on_conflict_do_update(
            index_elements=["tournament_id", "player_id"],
            set_={
                "composite_score": s["composite_score"],
                "computed_at": now,
            },
        )
        db.execute(stmt)

    db.commit()
    logger.info("Computed fit scores for %d players", len(scores))
    return scores


def compute_comparison_delta(player_stat: float, winner_avg: float) -> float:
    """Compute the delta between a player's stat and the historical winner average."""
    return player_stat - winner_avg


def is_highlighted(delta: float, threshold: float) -> bool:
    """Determine if a stat delta should be highlighted (exceeds threshold)."""
    return abs(delta) > threshold


def filter_rankings(
    rankings: list[dict],
    min_rank: Optional[int] = None,
    min_score: Optional[float] = None,
    max_results: Optional[int] = None,
) -> list[dict]:
    """
    Filter player rankings by criteria.
    Result is always a subset of the input rankings.
    """
    filtered = list(rankings)

    if min_rank is not None:
        filtered = [
            r for r in filtered
            if r.get("world_ranking") is not None and r["world_ranking"] <= min_rank
        ]

    if min_score is not None:
        filtered = [r for r in filtered if r["composite_score"] >= min_score]

    if max_results is not None:
        filtered = filtered[:max_results]

    return filtered
