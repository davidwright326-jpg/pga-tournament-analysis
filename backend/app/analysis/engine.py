"""Course stat importance analysis using Spearman rank correlation."""
import logging
from typing import Optional

import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy.orm import Session

from app.config import REQUIRED_STAT_KEYS, MIN_HISTORICAL_SEASONS
from app.models import TournamentResult, PlayerStat, Tournament
from app.analysis.archetypes import classify_course_from_tournament, get_archetype_weights

logger = logging.getLogger(__name__)

# Explanation templates based on stat weight ranking
EXPLANATIONS = {
    "sg_total": "Overall strokes gained is a strong predictor at this course",
    "sg_off_tee": "Tee shot quality matters here — course rewards good driving",
    "sg_approach": "Approach play is critical — precise iron play separates contenders",
    "sg_around_green": "Short game is key — complex green surrounds demand creativity",
    "sg_putting": "Putting surfaces reward strong putters at this venue",
    "sg_tee_to_green": "Ball-striking from tee to green is the primary differentiator",
    "driving_distance": "Length off the tee provides a significant advantage here",
    "driving_accuracy": "Narrow fairways favor driving accuracy over distance",
    "gir": "Hitting greens in regulation is essential on this course",
    "scrambling": "Recovery ability matters — missing greens is punished less for good scramblers",
    "birdie_avg": "Birdie-making ability separates winners at this venue",
    "scoring_avg": "Low scoring is the baseline requirement for contention",
}


def _parse_position(pos: str) -> Optional[int]:
    """Convert position string to numeric rank. Returns None for CUT/WD/DQ."""
    if not pos:
        return None
    pos = pos.strip().upper()
    if pos in ("CUT", "WD", "DQ", "MDF"):
        return None
    pos = pos.lstrip("T")
    try:
        return int(pos)
    except ValueError:
        return None


def compute_stat_weights_from_data(
    results: list[dict], player_stats: list[dict]
) -> dict[str, float]:
    """
    Pure function: compute stat weights from pre-fetched data.
    
    Args:
        results: list of dicts with keys: player_id, position (numeric)
        player_stats: list of dicts with keys: player_id, stat_category, stat_value
    
    Returns:
        dict mapping stat_category -> normalized weight (0-1, sum to 1.0)
    """
    if not results or not player_stats:
        # Return uniform weights if no data
        uniform = 1.0 / len(REQUIRED_STAT_KEYS)
        return {k: uniform for k in REQUIRED_STAT_KEYS}

    # Build DataFrames
    results_df = pd.DataFrame(results)
    stats_df = pd.DataFrame(player_stats)

    correlations = {}
    for cat in REQUIRED_STAT_KEYS:
        cat_stats = stats_df[stats_df["stat_category"] == cat]
        if cat_stats.empty:
            correlations[cat] = 0.0
            continue

        merged = results_df.merge(cat_stats, on="player_id", how="inner")
        if len(merged) < 5:
            correlations[cat] = 0.0
            continue

        positions = merged["position"].values
        values = merged["stat_value"].values

        try:
            corr, _ = spearmanr(values, positions)
            # Negative correlation means higher stat -> lower (better) position
            # We want the absolute value as importance
            correlations[cat] = abs(corr) if pd.notna(corr) else 0.0
        except Exception:
            correlations[cat] = 0.0

    # Normalize weights to sum to 1.0
    total = sum(correlations.values())
    if total == 0:
        uniform = 1.0 / len(REQUIRED_STAT_KEYS)
        return {k: uniform for k in REQUIRED_STAT_KEYS}

    return {k: v / total for k, v in correlations.items()}


def compute_stat_weights(
    tournament_id: str, seasons: list[int], db: Session
) -> dict[str, float]:
    """
    Compute stat importance weights for a tournament using historical data.
    Queries the database for results and stats, then delegates to pure function.

    Falls back to course archetype weights when fewer than MIN_HISTORICAL_SEASONS
    seasons of data are available.
    """
    # Count distinct seasons with historical results for this tournament
    distinct_seasons = (
        db.query(TournamentResult.season)
        .filter(TournamentResult.tournament_id == tournament_id)
        .distinct()
        .count()
    )

    if distinct_seasons < MIN_HISTORICAL_SEASONS:
        # Fallback: classify course by archetype and use predefined weights
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if tournament:
            archetype = classify_course_from_tournament(tournament)
            logger.info(
                "Insufficient historical data for %s (%d seasons < %d). "
                "Using archetype fallback: %s",
                tournament_id, distinct_seasons, MIN_HISTORICAL_SEASONS, archetype,
            )
            return get_archetype_weights(archetype)
        else:
            logger.warning(
                "Tournament %s not found in DB. Using default archetype fallback.",
                tournament_id,
            )
            return get_archetype_weights("parkland_short")

    # Get top-10 finishers across seasons
    results_query = (
        db.query(TournamentResult)
        .filter(
            TournamentResult.tournament_id == tournament_id,
            TournamentResult.season.in_(seasons),
        )
        .all()
    )

    results = []
    for r in results_query:
        pos = _parse_position(r.position)
        if pos is not None and pos <= 10:
            results.append({"player_id": r.player_id, "position": pos})

    # Get player stats for those players/seasons
    player_ids = list({r["player_id"] for r in results})
    stats_query = (
        db.query(PlayerStat)
        .filter(
            PlayerStat.player_id.in_(player_ids),
            PlayerStat.season.in_(seasons),
        )
        .all()
    )

    player_stats = [
        {
            "player_id": s.player_id,
            "stat_category": s.stat_category,
            "stat_value": s.stat_value,
        }
        for s in stats_query
        if s.stat_value is not None
    ]

    weights = compute_stat_weights_from_data(results, player_stats)

    logger.info(
        "Computed stat weights for %s: %d results, %d stat rows",
        tournament_id, len(results), len(player_stats),
    )
    return weights


def generate_explanation(stat_key: str, weight: float, all_weights: dict[str, float]) -> str:
    """Generate an explanation for why a stat matters at this course."""
    sorted_stats = sorted(all_weights.items(), key=lambda x: x[1], reverse=True)
    rank = next(i for i, (k, _) in enumerate(sorted_stats) if k == stat_key) + 1

    base = EXPLANATIONS.get(stat_key, f"{stat_key} contributes to success at this course")

    if rank <= 3:
        return f"High importance: {base} (ranked #{rank} of {len(all_weights)} categories)"
    elif rank <= 6:
        return f"Moderate importance: {base} (ranked #{rank})"
    else:
        return f"Lower importance: {base} (ranked #{rank})"
