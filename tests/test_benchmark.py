from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import make_row

NOW = datetime.now(timezone.utc)


def setup_dynamo(session_mock, url: str | None = None, put_raises: Exception | None = None) -> AsyncMock:
    """Configure session_mock. Returns the table mock so callers can assert on it."""
    table = AsyncMock()
    table.get_item.return_value = {"Item": {"full_url": url}} if url else {}
    if put_raises:
        table.put_item.side_effect = put_raises
    else:
        table.put_item.return_value = {}

    resource = AsyncMock()
    resource.Table.return_value = table

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resource)
    cm.__aexit__ = AsyncMock(return_value=False)
    session_mock.resource.return_value = cm
    return table


def setup_dynamo_get_raises(session_mock, exc: Exception) -> AsyncMock:
    """Configure session_mock so get_item raises exc."""
    table = AsyncMock()
    table.get_item.side_effect = exc
    table.put_item.return_value = {}

    resource = AsyncMock()
    resource.Table.return_value = table

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resource)
    cm.__aexit__ = AsyncMock(return_value=False)
    session_mock.resource.return_value = cm
    return table


class TestBenchmarkLookup:
    def test_returns_timings_and_null_errors_on_success(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.return_value = "https://example.com"
        mock_pool.fetchrow.return_value = make_row(full_url="https://example.com")
        setup_dynamo(mock_dynamo_session, url="https://example.com")

        resp = client.get("/api/benchmark/lookup/abc")

        assert resp.status_code == 200
        data = resp.json()
        assert data["short_code"] == "abc"
        assert data["full_url"] == "https://example.com"
        assert "redis_ms" in data and "postgres_ms" in data and "dynamo_ms" in data
        assert data["redis_error"] is None
        assert data["postgres_error"] is None
        assert data["dynamo_error"] is None
        assert data["winner"] in ("redis", "postgres", "dynamo")

    def test_surfaces_redis_error(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.side_effect = Exception("invalid username-password pair")
        mock_pool.fetchrow.return_value = make_row(full_url="https://example.com")
        setup_dynamo(mock_dynamo_session, url="https://example.com")

        resp = client.get("/api/benchmark/lookup/abc")

        assert resp.status_code == 200
        data = resp.json()
        assert data["redis_error"] == "invalid username-password pair"
        assert data["postgres_error"] is None
        assert data["dynamo_error"] is None
        assert data["winner"] in ("postgres", "dynamo")

    def test_surfaces_dynamo_error(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.return_value = "https://example.com"
        mock_pool.fetchrow.return_value = make_row(full_url="https://example.com")
        setup_dynamo_get_raises(mock_dynamo_session, Exception("ValidationException: key mismatch"))

        resp = client.get("/api/benchmark/lookup/abc")

        assert resp.status_code == 200
        data = resp.json()
        assert data["dynamo_error"] == "ValidationException: key mismatch"
        assert data["redis_error"] is None
        assert data["winner"] in ("redis", "postgres")

    def test_winner_excludes_errored_stores(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.side_effect = Exception("auth error")
        mock_pool.fetchrow.return_value = make_row(full_url="https://example.com")
        setup_dynamo(mock_dynamo_session, url="https://example.com")

        data = client.get("/api/benchmark/lookup/abc").json()

        assert data["winner"] in ("postgres", "dynamo")
        assert data["winner"] != "redis"

    def test_resolves_url_from_any_store(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.return_value = None
        mock_pool.fetchrow.return_value = None
        setup_dynamo(mock_dynamo_session, url="https://dynamo-only.com")

        resp = client.get("/api/benchmark/lookup/abc")

        assert resp.status_code == 200
        assert resp.json()["full_url"] == "https://dynamo-only.com"

    def test_not_found_returns_null_full_url(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.return_value = None
        mock_pool.fetchrow.return_value = None
        setup_dynamo(mock_dynamo_session, url=None)

        resp = client.get("/api/benchmark/lookup/nonexistent")

        assert resp.status_code == 200
        assert resp.json()["full_url"] is None
        assert resp.json()["winner"] is not None  # stores responded, just no URL

    def test_all_stores_error_sets_winner_none(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_redis.get.side_effect = Exception("redis down")
        mock_pool.fetchrow.side_effect = Exception("postgres down")
        setup_dynamo_get_raises(mock_dynamo_session, Exception("dynamo down"))

        data = client.get("/api/benchmark/lookup/abc").json()

        assert data["winner"] is None
        assert data["redis_error"] is not None
        assert data["postgres_error"] is not None
        assert data["dynamo_error"] is not None


class TestBenchmarkShorten:
    def test_new_url_writes_to_all_three_stores(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_pool.fetchrow.return_value = None
        mock_pool.execute.return_value = None
        table = setup_dynamo(mock_dynamo_session)

        resp = client.post("/api/benchmark/shorten", json={"full_url": "https://example.com"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["postgres_write_error"] is None
        assert data["dynamo_write_error"] is None
        assert data["redis_write_error"] is None
        table.put_item.assert_called_once()
        mock_redis.setex.assert_called_once()

    def test_surfaces_dynamo_write_error(self, client, mock_pool, mock_dynamo_session):
        mock_pool.fetchrow.return_value = make_row(short_code="abc")
        setup_dynamo(mock_dynamo_session, put_raises=Exception("ValidationException: missing key"))

        data = client.post("/api/benchmark/shorten", json={"full_url": "https://example.com"}).json()

        assert data["dynamo_write_error"] == "ValidationException: missing key"
        assert data["postgres_write_error"] is None

    def test_surfaces_redis_write_error(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_pool.fetchrow.return_value = make_row(short_code="abc")
        mock_redis.setex.side_effect = Exception("auth error")
        setup_dynamo(mock_dynamo_session)

        data = client.post("/api/benchmark/shorten", json={"full_url": "https://example.com"}).json()

        assert data["redis_write_error"] == "auth error"
        assert data["dynamo_write_error"] is None

    def test_existing_url_skips_postgres_insert(self, client, mock_pool, mock_redis, mock_dynamo_session):
        mock_pool.fetchrow.return_value = make_row(short_code="abc")
        setup_dynamo(mock_dynamo_session)

        resp = client.post("/api/benchmark/shorten", json={"full_url": "https://example.com"})

        assert resp.status_code == 200
        assert resp.json()["short_code"] == "abc"
        mock_pool.execute.assert_not_called()

    def test_invalid_url_returns_422(self, client, mock_dynamo_session):
        setup_dynamo(mock_dynamo_session)

        resp = client.post("/api/benchmark/shorten", json={"full_url": "not-a-url"})

        assert resp.status_code == 422

