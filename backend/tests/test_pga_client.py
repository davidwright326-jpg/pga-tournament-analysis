"""Unit tests for PGA Tour GraphQL client."""
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from app.data.pga_client import (
    _graphql_request,
    fetch_tournament_schedule,
    fetch_past_results,
    fetch_stat_details,
    fetch_available_seasons,
    fetch_event_stat_details,
    HEADERS,
    MAX_RETRIES,
)


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    resp.request = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=resp.request, response=resp
        )
    return resp


class TestGraphQLRequest:
    """Tests for the core _graphql_request helper."""

    @pytest.mark.asyncio
    async def test_successful_request(self):
        payload = {"operationName": "Test", "query": "{ test }"}
        mock_resp = _mock_response({"data": {"test": "value"}})

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _graphql_request(payload)

        assert result == {"test": "value"}
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_graphql_error_raises_value_error(self):
        payload = {"operationName": "Test", "query": "{ test }"}
        mock_resp = _mock_response({"data": {}, "errors": [{"message": "bad query"}]})

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="GraphQL error"):
                await _graphql_request(payload)

    @pytest.mark.asyncio
    async def test_non_retryable_http_error_propagates(self):
        payload = {"operationName": "Test", "query": "{ test }"}
        mock_resp = _mock_response({}, status_code=403)

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.HTTPStatusError):
                await _graphql_request(payload)

    @pytest.mark.asyncio
    async def test_retries_on_429(self):
        """Should retry on 429 and succeed on subsequent attempt."""
        payload = {"operationName": "Test", "query": "{ test }"}
        rate_limited_resp = MagicMock(spec=httpx.Response)
        rate_limited_resp.status_code = 429
        rate_limited_resp.request = MagicMock()

        success_resp = _mock_response({"data": {"ok": True}})

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls, \
             patch("app.data.pga_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [rate_limited_resp, success_resp]
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _graphql_request(payload)

        assert result == {"ok": True}
        assert mock_client.post.call_count == 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_500(self):
        """Should retry on 500 server errors."""
        payload = {"operationName": "Test", "query": "{ test }"}
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.status_code = 500
        error_resp.request = MagicMock()

        success_resp = _mock_response({"data": {"recovered": True}})

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls, \
             patch("app.data.pga_client.asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.post.side_effect = [error_resp, success_resp]
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _graphql_request(payload)

        assert result == {"recovered": True}

    @pytest.mark.asyncio
    async def test_retries_exhausted_raises(self):
        """Should raise after all retries are exhausted."""
        payload = {"operationName": "Test", "query": "{ test }"}
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.status_code = 503
        error_resp.request = MagicMock()

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls, \
             patch("app.data.pga_client.asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.post.return_value = error_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.HTTPStatusError):
                await _graphql_request(payload)

        assert mock_client.post.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        """Should retry on timeout exceptions."""
        payload = {"operationName": "Test", "query": "{ test }"}
        success_resp = _mock_response({"data": {"ok": True}})

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls, \
             patch("app.data.pga_client.asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.post.side_effect = [
                httpx.TimeoutException("timed out"),
                success_resp,
            ]
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _graphql_request(payload)

        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty_dict(self):
        payload = {"operationName": "Test", "query": "{ test }"}
        mock_resp = _mock_response({"data": {}})

        with patch("app.data.pga_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _graphql_request(payload)

        assert result == {}


class TestFetchTournamentSchedule:
    """Tests for fetch_tournament_schedule."""

    @pytest.mark.asyncio
    async def test_parses_completed_and_upcoming(self):
        api_data = {
            "schedule": {
                "completed": [
                    {"tournaments": [
                        {"id": "R001", "tournamentName": "The Masters", "city": "Augusta",
                         "state": "GA", "country": "US", "courseName": "Augusta National",
                         "startDate": "2025-04-10", "purse": 20000000},
                    ]},
                ],
                "upcoming": [
                    {"tournaments": [
                        {"id": "R002", "tournamentName": "PGA Championship", "city": "Louisville",
                         "state": "KY", "country": "US", "courseName": "Valhalla",
                         "startDate": "2025-05-15", "purse": 17500000},
                    ]},
                ],
            }
        }

        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = api_data
            result = await fetch_tournament_schedule(2025)

        assert len(result) == 2
        assert result[0]["id"] == "R001"
        assert result[1]["id"] == "R002"

    @pytest.mark.asyncio
    async def test_handles_empty_schedule(self):
        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"schedule": {"completed": [], "upcoming": []}}
            result = await fetch_tournament_schedule(2025)

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_dict_section_format(self):
        """Handle case where section_data is a dict instead of list."""
        api_data = {
            "schedule": {
                "completed": {"tournaments": [{"id": "R001", "tournamentName": "Test"}]},
                "upcoming": [],
            }
        }

        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = api_data
            result = await fetch_tournament_schedule(2025)

        assert len(result) == 1
        assert result[0]["id"] == "R001"


class TestFetchPastResults:
    """Tests for fetch_past_results."""

    @pytest.mark.asyncio
    async def test_returns_tournament_results(self):
        api_data = {
            "tournamentPastResults": {
                "id": "R001-2024",
                "players": [
                    {
                        "id": "p1", "position": "1",
                        "player": {"id": "p1", "firstName": "Scottie", "lastName": "Scheffler", "displayName": "Scottie Scheffler"},
                        "rounds": [{"score": 67, "parRelativeScore": -5}],
                        "additionalData": "", "total": 268, "parRelativeScore": -20,
                    }
                ],
                "winner": {"id": "p1", "firstName": "Scottie", "lastName": "Scheffler", "totalStrokes": 268, "totalScore": -20},
            }
        }

        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = api_data
            result = await fetch_past_results("R001", 20240)

        assert result["id"] == "R001-2024"
        assert len(result["players"]) == 1
        assert result["winner"]["id"] == "p1"

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_results(self):
        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            result = await fetch_past_results("R999", 20240)

        assert result == {}


class TestFetchStatDetails:
    """Tests for fetch_stat_details."""

    @pytest.mark.asyncio
    async def test_returns_player_rows_only(self):
        api_data = {
            "statDetails": {
                "tourCode": "R", "statId": "02675", "statType": "STROKES_GAINED",
                "rows": [
                    {"__typename": "StatDetailsPlayer", "playerId": "p1",
                     "playerName": "Scottie Scheffler", "country": "USA", "rank": "1",
                     "stats": [{"statName": "SG: Total", "statValue": "2.50"}]},
                    {"__typename": "StatDetailsTourAvg", "stats": [{"statName": "Tour Avg", "statValue": "0.00"}]},
                ],
            }
        }

        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = api_data
            result = await fetch_stat_details("02675", 2025)

        assert len(result) == 1
        assert result[0]["playerId"] == "p1"
        assert result[0]["__typename"] == "StatDetailsPlayer"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rows(self):
        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"statDetails": {"rows": []}}
            result = await fetch_stat_details("02675", 2025)

        assert result == []


class TestFetchAvailableSeasons:
    """Tests for fetch_available_seasons."""

    @pytest.mark.asyncio
    async def test_returns_seasons_list(self):
        api_data = {
            "tournamentPastResults": {
                "availableSeasons": [
                    {"year": 20250, "displaySeason": "2025"},
                    {"year": 20240, "displaySeason": "2024"},
                ]
            }
        }

        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = api_data
            result = await fetch_available_seasons("R001")

        assert len(result) == 2
        assert result[0]["year"] == 20250


class TestFetchEventStatDetails:
    """Tests for fetch_event_stat_details."""

    @pytest.mark.asyncio
    async def test_returns_player_rows_for_event(self):
        api_data = {
            "statDetails": {
                "tourCode": "R", "statId": "02675", "statType": "STROKES_GAINED",
                "rows": [
                    {"__typename": "StatDetailsPlayer", "playerId": "p1",
                     "playerName": "Test Player", "country": "USA", "rank": "1",
                     "stats": [{"statName": "SG: Total", "statValue": "3.00"}]},
                ],
            }
        }

        with patch("app.data.pga_client._graphql_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = api_data
            result = await fetch_event_stat_details("02675", 2025, "R001-2025")

        assert len(result) == 1
        assert result[0]["playerId"] == "p1"


class TestHeaders:
    """Tests for API configuration."""

    def test_headers_contain_api_key(self):
        assert "x-api-key" in HEADERS
        assert HEADERS["x-api-key"] is not None
        assert len(HEADERS["x-api-key"]) > 0

    def test_headers_contain_content_type(self):
        assert HEADERS["Content-Type"] == "application/json"
