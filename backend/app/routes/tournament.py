"""Tournament API endpoints."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tournament, CourseStatWeight, TournamentResult, PlayerStat, EventPlayerStat
from app.data.tournament_resolver import resolve_current_tournament
from app.analysis.engine import generate_explanation
from app.config import STAT_CATEGORIES

router = APIRouter()


@router.get("/current")
def get_current_tournament(db: Session = Depends(get_db)):
    """Get the current week's tournament details."""
    tournaments = db.query(Tournament).order_by(Tournament.start_date).all()
    current = resolve_current_tournament(date.today(), tournaments)

    if not current:
        return {
            "tournament": None,
            "message": "No tournament scheduled. Check back for the next event.",
            "next_event": _get_next_event(tournaments),
        }

    return {
        "tournament": _serialize_tournament(current),
        "message": None,
    }


@router.get("/{tournament_id}/stats")
def get_tournament_stats(tournament_id: str, db: Session = Depends(get_db)):
    """Get stat importance weights for a tournament."""
    weights = (
        db.query(CourseStatWeight)
        .filter(CourseStatWeight.tournament_id == tournament_id)
        .all()
    )

    if not weights:
        raise HTTPException(404, "No stat weights computed for this tournament")

    result = []
    weight_dict = {w.stat_category: w.weight for w in weights}
    for w in weights:
        cat_info = STAT_CATEGORIES.get(w.stat_category, {})
        result.append({
            "category": w.stat_category,
            "display_name": cat_info.get("name", w.stat_category),
            "weight": w.weight,
            "explanation": w.explanation or generate_explanation(
                w.stat_category, w.weight, weight_dict
            ),
        })

    result.sort(key=lambda x: x["weight"], reverse=True)
    return {"stats": result, "tournament_id": tournament_id}


@router.get("/{tournament_id}/history")
def get_tournament_history(
    tournament_id: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Get past winners and their stats for a tournament."""
    from datetime import date as date_type
    current_year = date_type.today().year

    # Get winners (position = "1") across past seasons (exclude current year)
    winners = (
        db.query(TournamentResult)
        .filter(
            TournamentResult.tournament_id == tournament_id,
            TournamentResult.position == "1",
            TournamentResult.season < current_year,
        )
        .order_by(TournamentResult.season.desc())
        .all()
    )

    # Deduplicate by season (keep first entry per season)
    seen_seasons = set()
    unique_winners = []
    for w in winners:
        if w.season not in seen_seasons:
            seen_seasons.add(w.season)
            unique_winners.append(w)
    unique_winners = unique_winners[:limit]

    result = []
    for w in unique_winners:
        # Get event-level stats (stats from the week they won)
        event_stats = (
            db.query(EventPlayerStat)
            .filter(
                EventPlayerStat.player_id == w.player_id,
                EventPlayerStat.season == w.season,
            )
            .all()
        )
        stat_dict = {s.stat_category: s.stat_value for s in event_stats if s.stat_value is not None}
        stat_ranks = {s.stat_category: s.stat_rank for s in event_stats if s.stat_rank is not None}

        # Fall back to season stats if no event stats
        if not stat_dict:
            stats = (
                db.query(PlayerStat)
                .filter(PlayerStat.player_id == w.player_id)
                .order_by(PlayerStat.season.desc())
                .all()
            )
            for s in stats:
                if s.stat_category not in stat_dict and s.stat_value is not None:
                    stat_dict[s.stat_category] = s.stat_value
                if s.stat_category not in stat_ranks and s.stat_rank is not None:
                    stat_ranks[s.stat_category] = s.stat_rank

        result.append({
            "season": w.season,
            "player_id": w.player_id,
            "player_name": w.player_name,
            "position": w.position,
            "total_score": w.total_score,
            "par_relative_score": w.par_relative_score,
            "stats": stat_dict,
            "stat_ranks": stat_ranks,
        })

    return {"history": result, "tournament_id": tournament_id}


def _serialize_tournament(t: Tournament) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "course_name": t.course_name,
        "city": t.city,
        "state": t.state,
        "country": t.country,
        "par": t.par,
        "yardage": t.yardage,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "end_date": t.end_date.isoformat() if t.end_date else None,
        "season": t.season,
        "purse": t.purse,
    }


def _get_next_event(tournaments: list[Tournament]) -> Optional[dict]:
    today = date.today()
    upcoming = [t for t in tournaments if t.start_date > today]
    if upcoming:
        upcoming.sort(key=lambda t: t.start_date)
        return _serialize_tournament(upcoming[0])
    return None


@router.get("/season/{season}")
def get_season_results(season: int, db: Session = Depends(get_db)):
    """Get all completed tournaments for a season with their winners."""
    today = date.today()

    # Get all tournaments for this season that have already started
    tournaments = (
        db.query(Tournament)
        .filter(Tournament.season == season, Tournament.start_date <= today)
        .order_by(Tournament.start_date.desc())
        .all()
    )

    results = []
    for t in tournaments:
        # Get the winner for this tournament
        winner = (
            db.query(TournamentResult)
            .filter(
                TournamentResult.tournament_id == t.id,
                TournamentResult.position == "1",
                TournamentResult.season == season,
            )
            .first()
        )

        # If no winner stored for this season, check any season (the ingestion
        # may have stored it under a different season number)
        if not winner:
            winner = (
                db.query(TournamentResult)
                .filter(
                    TournamentResult.tournament_id == t.id,
                    TournamentResult.position == "1",
                )
                .first()
            )

        winner_info = None
        if winner:
            winner_info = {
                "player_id": winner.player_id,
                "player_name": winner.player_name,
                "total_score": winner.total_score,
                "par_relative_score": winner.par_relative_score,
            }

        results.append({
            "tournament": _serialize_tournament(t),
            "winner": winner_info,
        })

    return {"season": season, "results": results, "total": len(results)}
