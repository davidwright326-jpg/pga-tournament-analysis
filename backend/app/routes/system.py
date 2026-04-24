"""System endpoints - refresh and status."""
import asyncio
import logging
import threading
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory status tracking
_refresh_status = {
    "last_refresh": None,
    "status": "idle",
    "error": None,
}


def _run_refresh_sync():
    """Execute the full data refresh pipeline synchronously in a background thread."""
    from app.data.ingestion import ingest_schedule, ingest_player_stats, ingest_past_results, ingest_event_stats, ingest_season_winners
    from app.data.tournament_resolver import resolve_current_tournament
    from app.data import pga_client
    from app.analysis.engine import compute_stat_weights, generate_explanation
    from app.analysis.scoring import compute_all_fit_scores
    from app.models import Tournament, CourseStatWeight
    from app.config import DEFAULT_LOOKBACK_SEASONS
    from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
    from datetime import date

    current_year = date.today().year
    _refresh_status["status"] = "running"
    _refresh_status["error"] = None

    db = SessionLocal()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. Ingest schedule
        loop.run_until_complete(ingest_schedule(current_year, db))

        # 1b. Ingest winners for all completed tournaments this season
        loop.run_until_complete(ingest_season_winners(current_year, db))

        # 2. Find current tournament
        tournaments = db.query(Tournament).order_by(Tournament.start_date).all()
        current = resolve_current_tournament(date.today(), tournaments)
        if not current:
            _refresh_status["status"] = "completed"
            _refresh_status["last_refresh"] = datetime.utcnow().isoformat()
            logger.info("No current tournament found during refresh")
            return

        # 3. Ingest player stats
        loop.run_until_complete(ingest_player_stats(current_year, db))

        # 4. Ingest historical results
        seasons = list(range(current_year - DEFAULT_LOOKBACK_SEASONS, current_year + 1))
        loop.run_until_complete(ingest_past_results(current.id, seasons, db))

        # 4b. Ingest event-level stats for past winners
        # Get available seasons to build event ID mapping
        available = loop.run_until_complete(pga_client.fetch_available_seasons(current.id))
        seasons_info = []
        for s in available[:DEFAULT_LOOKBACK_SEASONS]:
            api_year = s.get("year")
            if api_year:
                real_year = api_year // 10 if api_year > 9999 else api_year
                # Fetch past results to get the season-specific tournament ID
                results = loop.run_until_complete(pga_client.fetch_past_results(current.id, api_year))
                event_id = results.get("id") if results else None
                if event_id:
                    seasons_info.append({
                        "api_year": api_year,
                        "real_year": real_year,
                        "event_id": event_id,
                    })
        if seasons_info:
            loop.run_until_complete(ingest_event_stats(current.id, seasons_info, db))

        # 5. Compute stat weights
        weights = compute_stat_weights(current.id, seasons, db)

        # Store weights
        for cat, weight in weights.items():
            explanation = generate_explanation(cat, weight, weights)
            stmt = sqlite_upsert(CourseStatWeight).values(
                tournament_id=current.id,
                stat_category=cat,
                weight=weight,
                explanation=explanation,
            ).on_conflict_do_update(
                index_elements=["tournament_id", "stat_category"],
                set_={"weight": weight, "explanation": explanation},
            )
            db.execute(stmt)
        db.commit()

        # 6. Compute fit scores
        compute_all_fit_scores(current.id, weights, current_year, db)

        _refresh_status["status"] = "completed"
        _refresh_status["last_refresh"] = datetime.utcnow().isoformat()
        logger.info("Refresh completed successfully")

    except Exception as e:
        _refresh_status["status"] = "error"
        _refresh_status["error"] = str(e)
        logger.error("Refresh failed: %s", e, exc_info=True)
    finally:
        db.close()
        loop.close()


@router.post("/refresh")
def trigger_refresh():
    """Trigger a manual data refresh in a background thread."""
    if _refresh_status["status"] == "running":
        return {"message": "Refresh already in progress", "status": _refresh_status}

    thread = threading.Thread(target=_run_refresh_sync, daemon=True)
    thread.start()
    return {"message": "Refresh started", "status": "running"}


@router.get("/status")
def get_status():
    """Get system status and last refresh time."""
    return {
        "status": _refresh_status["status"],
        "last_refresh": _refresh_status["last_refresh"],
        "error": _refresh_status["error"],
    }
