"""Data ingestion pipeline - fetches PGA data and stores in database."""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.orm import Session

from app.config import STAT_CATEGORIES
from app.data import pga_client
from app.models import Tournament, TournamentResult, PlayerStat

logger = logging.getLogger(__name__)


def _parse_timestamp(ts) -> datetime.date:
    """Parse a Unix timestamp in milliseconds to a date."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts / 1000).date()
    # Try ISO string fallback
    if isinstance(ts, str):
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
    return None


def _parse_purse(purse_str) -> float:
    """Parse purse string like '$9,100,000' to float."""
    if purse_str is None:
        return None
    if isinstance(purse_str, (int, float)):
        return float(purse_str)
    cleaned = re.sub(r'[^\d.]', '', str(purse_str))
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


async def ingest_schedule(season: int, db: Session):
    """Fetch tournament schedule and upsert into tournaments table."""
    logger.info("Ingesting schedule for season %d", season)
    tournaments = await pga_client.fetch_tournament_schedule(season)

    for t in tournaments:
        start_date = _parse_timestamp(t.get("startDate"))
        if not start_date:
            continue
        # PGA tournaments are typically 4 days (Thu-Sun)
        end_date = start_date + timedelta(days=3)

        stmt = sqlite_upsert(Tournament).values(
            id=t.get("id", ""),
            name=t.get("tournamentName", ""),
            course_name=t.get("courseName", ""),
            city=t.get("city"),
            state=t.get("state"),
            country=t.get("country"),
            start_date=start_date,
            end_date=end_date,
            season=season,
            purse=_parse_purse(t.get("purse")),
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": t.get("tournamentName", ""),
                "course_name": t.get("courseName", ""),
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        db.execute(stmt)

    db.commit()
    logger.info("Ingested %d tournaments for season %d", len(tournaments), season)


async def ingest_player_stats(season: int, db: Session):
    """Fetch all 12 stat categories and upsert into player_stats."""
    logger.info("Ingesting player stats for season %d", season)
    total_rows = 0

    for cat_key, cat_info in STAT_CATEGORIES.items():
        try:
            rows = await pga_client.fetch_stat_details(cat_info["pga_id"], season)
            for row in rows:
                player_id = row.get("playerId", "")
                if not player_id:
                    continue
                stat_value = None
                stats = row.get("stats", [])
                if stats:
                    raw = stats[0].get("statValue", "")
                    try:
                        cleaned = str(raw).replace(",", "").replace("%", "").strip()
                        stat_value = float(cleaned)
                    except (ValueError, TypeError):
                        stat_value = None

                stmt = sqlite_upsert(PlayerStat).values(
                    player_id=player_id,
                    player_name=row.get("playerName", ""),
                    season=season,
                    stat_category=cat_key,
                    stat_value=stat_value,
                    stat_rank=row.get("rank"),
                ).on_conflict_do_update(
                    index_elements=["player_id", "season", "stat_category"],
                    set_={"stat_value": stat_value, "stat_rank": row.get("rank")},
                )
                db.execute(stmt)
                total_rows += 1

            logger.info("Ingested %d rows for %s", len(rows), cat_key)
        except Exception as e:
            logger.error("Failed to ingest stat %s: %s", cat_key, e)

    db.commit()
    logger.info("Total player stat rows ingested: %d", total_rows)


async def ingest_past_results(tournament_id: str, seasons: list[int], db: Session):
    """Fetch historical results for a tournament using available seasons from the API."""
    logger.info("Ingesting past results for %s", tournament_id)
    total = 0

    # First, get available seasons from the API (they use a special year format like 20250)
    try:
        available = await pga_client.fetch_available_seasons(tournament_id)
    except Exception as e:
        logger.error("Failed to fetch available seasons for %s: %s", tournament_id, e)
        return

    # Limit to the requested number of seasons
    max_seasons = len(seasons)
    available = available[:max_seasons]

    for season_info in available:
        api_year = season_info.get("year")
        display = season_info.get("displaySeason", str(api_year))
        # Convert API year (e.g., 20250) to real year (e.g., 2025)
        real_year = api_year // 10 if api_year and api_year > 9999 else api_year

        if not api_year:
            continue

        try:
            results = await pga_client.fetch_past_results(tournament_id, api_year)
            if not results:
                continue
            players = results.get("players", [])
            if not players:
                continue

            for p in players:
                player_info = p.get("player", {})
                player_id = player_info.get("id", "")
                if not player_id:
                    continue

                position = p.get("position", "")
                rounds = p.get("rounds", [])

                stmt = sqlite_upsert(TournamentResult).values(
                    tournament_id=tournament_id,
                    season=real_year,
                    player_id=player_id,
                    player_name=player_info.get("displayName", ""),
                    position=position,
                    total_score=p.get("total"),
                    par_relative_score=p.get("parRelativeScore"),
                    rounds_played=len(rounds),
                ).on_conflict_do_update(
                    index_elements=["tournament_id", "season", "player_id"],
                    set_={
                        "position": position,
                        "total_score": p.get("total"),
                        "par_relative_score": p.get("parRelativeScore"),
                    },
                )
                db.execute(stmt)
                total += 1

            logger.info("Ingested %d results for %s season %s (%d)", len(players), tournament_id, display, real_year)
        except Exception as e:
            logger.error("Failed to ingest results for %s season %s: %s", tournament_id, display, e)

    db.commit()
    logger.info("Total result rows ingested: %d", total)


# Key stats to fetch at event level (the ones most commonly available per-event)
EVENT_STAT_IDS = {
    "sg_total": "02675",
    "sg_off_tee": "02567",
    "sg_approach": "02568",
    "sg_around_green": "02569",
    "sg_putting": "02564",
    "sg_tee_to_green": "02674",
    "driving_distance": "101",
    "driving_accuracy": "102",
    "gir": "103",
    "scrambling": "130",
    "birdie_avg": "156",
    "scoring_avg": "120",
}


async def ingest_event_stats(tournament_id: str, seasons_info: list[dict], db: Session):
    """
    Fetch event-level stats for past tournament winners.
    seasons_info: list of dicts with 'api_year', 'real_year', 'event_id' from past results.
    """
    from app.models import EventPlayerStat

    logger.info("Ingesting event stats for %s across %d seasons", tournament_id, len(seasons_info))
    total = 0

    for info in seasons_info:
        event_id = info.get("event_id")
        real_year = info.get("real_year")
        api_year = info.get("api_year")

        if not event_id or not real_year:
            continue

        for cat_key, stat_id in EVENT_STAT_IDS.items():
            try:
                rows = await pga_client.fetch_event_stat_details(stat_id, api_year, event_id)
                for row in rows:
                    player_id = row.get("playerId", "")
                    if not player_id:
                        continue

                    stat_value = None
                    stats = row.get("stats", [])
                    if stats:
                        # First stat is usually the average/primary value
                        raw = stats[0].get("statValue", "")
                        try:
                            cleaned = str(raw).replace(",", "").replace("%", "").strip()
                            stat_value = float(cleaned)
                        except (ValueError, TypeError):
                            stat_value = None

                    stmt = sqlite_upsert(EventPlayerStat).values(
                        tournament_id=event_id,
                        season=real_year,
                        player_id=player_id,
                        player_name=row.get("playerName", ""),
                        stat_category=cat_key,
                        stat_value=stat_value,
                        stat_rank=row.get("rank"),
                    ).on_conflict_do_update(
                        index_elements=["tournament_id", "season", "player_id", "stat_category"],
                        set_={"stat_value": stat_value, "stat_rank": row.get("rank")},
                    )
                    db.execute(stmt)
                    total += 1

            except Exception as e:
                logger.error("Failed to ingest event stat %s for %s year %d: %s", cat_key, event_id, real_year, e)

        logger.info("Ingested event stats for %s season %d", event_id, real_year)

    db.commit()
    logger.info("Total event stat rows ingested: %d", total)


async def ingest_season_winners(season: int, db: Session):
    """Fetch the most recent results (winners) for all tournaments in a season."""
    from app.models import Tournament
    from datetime import date as date_type

    today = date_type.today()

    # Get all completed tournaments this season
    completed = (
        db.query(Tournament)
        .filter(Tournament.season == season, Tournament.end_date < today)
        .order_by(Tournament.start_date)
        .all()
    )

    logger.info("Fetching winners for %d completed tournaments in %d", len(completed), season)
    total = 0

    for t in completed:
        # Check if we already have results for this tournament+season
        existing = (
            db.query(TournamentResult)
            .filter(
                TournamentResult.tournament_id == t.id,
                TournamentResult.season == season,
                TournamentResult.position == "1",
            )
            .first()
        )
        if existing:
            continue  # Already have winner data

        try:
            # Fetch the most recent results (no year param = current/latest)
            results = await pga_client.fetch_past_results(t.id, None)
            if not results:
                continue
            players = results.get("players", [])
            if not players:
                continue

            for p in players:
                player_info = p.get("player", {})
                player_id = player_info.get("id", "")
                if not player_id:
                    continue

                position = p.get("position", "")
                rounds = p.get("rounds", [])

                stmt = sqlite_upsert(TournamentResult).values(
                    tournament_id=t.id,
                    season=season,
                    player_id=player_id,
                    player_name=player_info.get("displayName", ""),
                    position=position,
                    total_score=p.get("total"),
                    par_relative_score=p.get("parRelativeScore"),
                    rounds_played=len(rounds),
                ).on_conflict_do_update(
                    index_elements=["tournament_id", "season", "player_id"],
                    set_={
                        "position": position,
                        "total_score": p.get("total"),
                        "par_relative_score": p.get("parRelativeScore"),
                    },
                )
                db.execute(stmt)
                total += 1

            logger.info("Ingested %d results for %s (%s)", len(players), t.name, t.id)
        except Exception as e:
            logger.error("Failed to ingest results for %s: %s", t.id, e)

    db.commit()
    logger.info("Total season winner rows ingested: %d", total)
