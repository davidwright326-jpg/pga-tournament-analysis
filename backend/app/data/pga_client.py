"""Async client for PGA Tour GraphQL API."""
import asyncio
import logging
from typing import Any

import httpx

from app.config import PGA_GRAPHQL_URL, PGA_API_KEY

logger = logging.getLogger(__name__)

HEADERS = {
    "x-api-key": PGA_API_KEY,
    "Content-Type": "application/json",
}

# Rate limiting: max 5 concurrent requests
_semaphore = asyncio.Semaphore(5)

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def _graphql_request(payload: dict) -> dict[str, Any]:
    """Execute a GraphQL request with rate limiting, retries, and error handling.

    Retries up to MAX_RETRIES times on transient HTTP errors (429, 5xx)
    with exponential backoff. Rate-limited via an asyncio semaphore.
    """
    operation = payload.get("operationName", "unknown")
    async with _semaphore:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(
                    "GraphQL request %s (attempt %d/%d)",
                    operation, attempt, MAX_RETRIES,
                )
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        PGA_GRAPHQL_URL, json=payload, headers=HEADERS
                    )

                    # Retry on transient HTTP errors
                    if resp.status_code in RETRYABLE_STATUS_CODES:
                        wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "Retryable HTTP %d for %s, retrying in %.1fs",
                            resp.status_code, operation, wait,
                        )
                        last_exc = httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    if "errors" in data:
                        logger.error("GraphQL errors for %s: %s", operation, data["errors"])
                        raise ValueError(f"GraphQL error: {data['errors']}")

                    logger.debug("GraphQL request %s succeeded", operation)
                    return data.get("data", {})

            except httpx.TimeoutException as exc:
                wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Timeout for %s (attempt %d/%d), retrying in %.1fs",
                    operation, attempt, MAX_RETRIES, wait,
                )
                last_exc = exc
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError:
                raise  # non-retryable HTTP errors propagate immediately
            except ValueError:
                raise  # GraphQL errors propagate immediately

        # All retries exhausted
        logger.error("All %d retries exhausted for %s", MAX_RETRIES, operation)
        raise last_exc or RuntimeError(f"Request failed after {MAX_RETRIES} retries")


async def fetch_tournament_schedule(season: int) -> list[dict]:
    """Fetch the tournament schedule for a given season."""
    payload = {
        "operationName": "Schedule",
        "variables": {"tourCode": "R", "year": str(season)},
        "query": """query Schedule($tourCode: String!, $year: String) {
          schedule(tourCode: $tourCode, year: $year) {
            completed { tournaments { id tournamentName city state country courseName startDate purse } }
            upcoming { tournaments { id tournamentName city state country courseName startDate purse } }
          }
        }""",
    }
    data = await _graphql_request(payload)
    schedule = data.get("schedule", {})
    tournaments = []
    for section in ["completed", "upcoming"]:
        section_data = schedule.get(section, [])
        # section_data is a list of groups, each with a "tournaments" key
        if isinstance(section_data, list):
            for group in section_data:
                if isinstance(group, dict) and "tournaments" in group:
                    tournaments.extend(group["tournaments"])
        elif isinstance(section_data, dict) and "tournaments" in section_data:
            tournaments.extend(section_data["tournaments"])
    return tournaments


async def fetch_available_seasons(tournament_id: str) -> list[dict]:
    """Fetch available seasons for a tournament's past results."""
    payload = {
        "operationName": "TournamentPastResults",
        "variables": {"tournamentPastResultsId": tournament_id, "year": None},
        "query": """query TournamentPastResults($tournamentPastResultsId: ID!, $year: Int) {
          tournamentPastResults(id: $tournamentPastResultsId, year: $year) {
            availableSeasons { year displaySeason }
          }
        }""",
    }
    data = await _graphql_request(payload)
    results = data.get("tournamentPastResults", {})
    return results.get("availableSeasons", [])


async def fetch_past_results(tournament_id: str, api_year: int) -> dict[str, Any]:
    """
    Fetch past results for a tournament.
    api_year should be the value from availableSeasons (e.g., 20250 for 2025).
    """
    payload = {
        "operationName": "TournamentPastResults",
        "variables": {"tournamentPastResultsId": tournament_id, "year": api_year},
        "query": """query TournamentPastResults($tournamentPastResultsId: ID!, $year: Int) {
          tournamentPastResults(id: $tournamentPastResultsId, year: $year) {
            id
            players {
              id position
              player { id firstName lastName displayName }
              rounds { score parRelativeScore }
              additionalData total parRelativeScore
            }
            winner { id firstName lastName totalStrokes totalScore }
          }
        }""",
    }
    data = await _graphql_request(payload)
    return data.get("tournamentPastResults", {})


async def fetch_stat_details(stat_id: str, season: int) -> list[dict]:
    """Fetch player stats for a specific stat category and season."""
    payload = {
        "operationName": "StatDetails",
        "variables": {
            "tourCode": "R",
            "statId": stat_id,
            "year": season,
            "eventQuery": None,
        },
        "query": """query StatDetails($tourCode: TourCode!, $statId: String!, $year: Int, $eventQuery: StatDetailEventQuery) {
          statDetails(tourCode: $tourCode, statId: $statId, year: $year, eventQuery: $eventQuery) {
            tourCode statId statType
            rows {
              ... on StatDetailsPlayer {
                __typename playerId playerName country rank
                stats { statName statValue }
              }
            }
          }
        }""",
    }
    data = await _graphql_request(payload)
    stat_details = data.get("statDetails", {})
    rows = stat_details.get("rows", [])
    # Filter out non-player rows (e.g., tour averages)
    return [r for r in rows if r.get("__typename") == "StatDetailsPlayer"]


async def fetch_event_stat_details(
    stat_id: str, season: int, tournament_id: str
) -> list[dict]:
    """Fetch player stats for a specific stat category at a specific tournament event."""
    payload = {
        "operationName": "StatDetails",
        "variables": {
            "tourCode": "R",
            "statId": stat_id,
            "year": season,
            "eventQuery": {"tournamentId": tournament_id, "queryType": "EVENT_ONLY"},
        },
        "query": """query StatDetails($tourCode: TourCode!, $statId: String!, $year: Int, $eventQuery: StatDetailEventQuery) {
          statDetails(tourCode: $tourCode, statId: $statId, year: $year, eventQuery: $eventQuery) {
            tourCode statId statType
            rows {
              ... on StatDetailsPlayer {
                __typename playerId playerName country rank
                stats { statName statValue }
              }
            }
          }
        }""",
    }
    data = await _graphql_request(payload)
    stat_details = data.get("statDetails", {})
    rows = stat_details.get("rows", [])
    return [r for r in rows if r.get("__typename") == "StatDetailsPlayer"]


async def fetch_tournament_field(tournament_id: str) -> list[dict]:
    """Fetch the official field for a tournament from the leaderboard/results."""
    # Try fetching current results (works for in-progress and completed events)
    payload = {
        "operationName": "Leaderboard",
        "variables": {"tournamentId": tournament_id},
        "query": """query Leaderboard($tournamentId: ID!) {
          leaderboardV2(id: $tournamentId) {
            players {
              player {
                id
                displayName
              }
            }
          }
        }""",
    }
    try:
        data = await _graphql_request(payload)
        leaderboard = data.get("leaderboardV2", {})
        players = leaderboard.get("players", [])
        result = []
        for p in players:
            player_info = p.get("player", {})
            pid = player_info.get("id", "")
            if pid:
                result.append({"player_id": pid, "player_name": player_info.get("displayName", "")})
        if result:
            return result
    except Exception as e:
        logger.warning("Leaderboard query failed for %s: %s", tournament_id, e)

    # Fallback: try the field/entry list query
    payload2 = {
        "operationName": "Field",
        "variables": {"tournamentId": tournament_id},
        "query": """query Field($tournamentId: ID!) {
          field(id: $tournamentId) {
            players {
              id
              displayName
            }
          }
        }""",
    }
    try:
        data = await _graphql_request(payload2)
        field = data.get("field", {})
        players = field.get("players", [])
        return [{"player_id": p.get("id", ""), "player_name": p.get("displayName", "")} for p in players if p.get("id")]
    except Exception as e:
        logger.warning("Field query also failed for %s: %s", tournament_id, e)
        return []
