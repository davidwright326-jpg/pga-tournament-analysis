"""Player API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlayerFitScore, PlayerStat, CourseStatWeight, TournamentResult
from app.config import STAT_CATEGORIES, HIGHLIGHT_THRESHOLD
from app.analysis.scoring import compute_comparison_delta, is_highlighted

router = APIRouter()


@router.get("/rankings")
def get_player_rankings(
    tournament_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    min_rank: Optional[int] = Query(None, description="Max world ranking (e.g. 50 = top 50)"),
    min_score: Optional[float] = Query(None),
    filter_stat: Optional[str] = Query(None, description="Only include players with a value for this stat category"),
    db: Session = Depends(get_db),
):
    """Get ranked player list with fit scores for a tournament."""
    query = (
        db.query(PlayerFitScore)
        .filter(PlayerFitScore.tournament_id == tournament_id)
        .order_by(PlayerFitScore.composite_score.desc())
    )

    if min_rank is not None:
        query = query.filter(
            PlayerFitScore.world_ranking.isnot(None),
            PlayerFitScore.world_ranking <= min_rank,
        )

    if min_score is not None:
        query = query.filter(PlayerFitScore.composite_score >= min_score)

    # If filter_stat is specified, join with player_stats to filter players
    # who have a non-null value for that stat category
    if filter_stat is not None:
        query = query.filter(
            PlayerFitScore.player_id.in_(
                db.query(PlayerStat.player_id)
                .filter(
                    PlayerStat.stat_category == filter_stat,
                    PlayerStat.stat_value.isnot(None),
                )
                .distinct()
            )
        )

    scores = query.limit(limit).all()

    # Get stat weights for context
    weights = (
        db.query(CourseStatWeight)
        .filter(CourseStatWeight.tournament_id == tournament_id)
        .all()
    )
    weight_cats = sorted(
        [(w.stat_category, w.weight) for w in weights],
        key=lambda x: x[1], reverse=True,
    )

    result = []
    for rank, s in enumerate(scores, 1):
        # Get player's individual stats and ranks (most recent season first)
        player_stats = (
            db.query(PlayerStat)
            .filter(PlayerStat.player_id == s.player_id)
            .order_by(PlayerStat.season.desc())
            .all()
        )
        stat_dict = {}
        stat_ranks = {}
        for ps in player_stats:
            if ps.stat_category not in stat_dict and ps.stat_value is not None:
                stat_dict[ps.stat_category] = ps.stat_value
                stat_ranks[ps.stat_category] = ps.stat_rank

        result.append({
            "rank": rank,
            "player_id": s.player_id,
            "player_name": s.player_name,
            "composite_score": s.composite_score,
            "world_ranking": s.world_ranking,
            "fedex_ranking": s.fedex_ranking,
            "stats": stat_dict,
            "stat_ranks": stat_ranks,
        })

    return {
        "rankings": result,
        "tournament_id": tournament_id,
        "total": len(result),
        "key_stats": [{"category": c, "weight": w} for c, w in weight_cats[:6]],
    }


@router.get("/{player_id}/profile")
def get_player_profile(
    player_id: str,
    tournament_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Get player detail with stat comparison to course ideal and historical winner avg."""
    # Get player fit score
    fit_score = (
        db.query(PlayerFitScore)
        .filter(
            PlayerFitScore.tournament_id == tournament_id,
            PlayerFitScore.player_id == player_id,
        )
        .first()
    )

    if not fit_score:
        raise HTTPException(404, "Player not found for this tournament")

    # Get player stats (most recent season)
    player_stats = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id)
        .order_by(PlayerStat.season.desc())
        .all()
    )
    stat_dict = {}
    for ps in player_stats:
        if ps.stat_category not in stat_dict and ps.stat_value is not None:
            stat_dict[ps.stat_category] = ps.stat_value

    # Get course stat weights
    weights = (
        db.query(CourseStatWeight)
        .filter(CourseStatWeight.tournament_id == tournament_id)
        .all()
    )
    weight_dict = {w.stat_category: w.weight for w in weights}

    # Get historical winner averages
    winners = (
        db.query(TournamentResult)
        .filter(
            TournamentResult.tournament_id == tournament_id,
            TournamentResult.position == "1",
        )
        .all()
    )

    winner_stats_agg: dict[str, list[float]] = {}
    for w in winners:
        w_stats = (
            db.query(PlayerStat)
            .filter(PlayerStat.player_id == w.player_id, PlayerStat.season == w.season)
            .all()
        )
        for ws in w_stats:
            if ws.stat_value is not None:
                winner_stats_agg.setdefault(ws.stat_category, []).append(ws.stat_value)

    winner_avgs = {k: sum(v) / len(v) for k, v in winner_stats_agg.items() if v}

    # Build comparison
    comparison = []
    for cat_key, cat_info in STAT_CATEGORIES.items():
        player_val = stat_dict.get(cat_key)
        winner_avg = winner_avgs.get(cat_key)
        weight = weight_dict.get(cat_key, 0)

        delta = None
        highlighted = False
        if player_val is not None and winner_avg is not None:
            delta = compute_comparison_delta(player_val, winner_avg)
            highlighted = is_highlighted(delta, HIGHLIGHT_THRESHOLD)

        comparison.append({
            "category": cat_key,
            "display_name": cat_info["name"],
            "player_value": player_val,
            "winner_avg": round(winner_avg, 3) if winner_avg else None,
            "delta": round(delta, 3) if delta is not None else None,
            "highlighted": highlighted,
            "weight": weight,
        })

    comparison.sort(key=lambda x: x["weight"], reverse=True)

    return {
        "player_id": player_id,
        "player_name": fit_score.player_name,
        "composite_score": fit_score.composite_score,
        "world_ranking": fit_score.world_ranking,
        "fedex_ranking": fit_score.fedex_ranking,
        "comparison": comparison,
        "tournament_id": tournament_id,
    }
