from datetime import datetime, timezone

import pytest

from tests.conftest import make_row

NOW = datetime.now(timezone.utc)


class TestShorten:
    def test_valid_url_creates_new(self, client, mock_pool):
        mock_pool.fetchrow.side_effect = [
            None,                        # dedup check — URL not seen before
            make_row(created_at=NOW),    # INSERT … RETURNING created_at
        ]

        resp = client.post("/api/shorten", json={"full_url": "https://example.com"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_new"] is True
        assert "short_code" in data
        assert data["short_url"].startswith("http")

    def test_deduplication_returns_existing(self, client, mock_pool):
        existing = make_row(
            id=1,
            short_code="abc",
            full_url="https://example.com/",
            created_at=NOW,
        )
        mock_pool.fetchrow.return_value = existing

        resp1 = client.post("/api/shorten", json={"full_url": "https://example.com"})
        resp2 = client.post("/api/shorten", json={"full_url": "https://example.com"})

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["short_code"] == resp2.json()["short_code"] == "abc"
        assert resp1.json()["is_new"] is False

    def test_invalid_url_returns_422(self, client):
        resp = client.post("/api/shorten", json={"full_url": "not-a-url"})
        assert resp.status_code == 422

    def test_missing_body_returns_422(self, client):
        resp = client.post("/api/shorten", json={})
        assert resp.status_code == 422


class TestRedirect:
    def test_cache_miss_redirects_via_db(self, client, mock_pool, mock_redis):
        mock_redis.get.return_value = None
        mock_pool.fetchrow.return_value = make_row(full_url="https://example.com")

        resp = client.get("/abc", follow_redirects=False)

        assert resp.status_code == 301
        assert resp.headers["location"] == "https://example.com"

    def test_cache_hit_redirects_without_db(self, client, mock_pool, mock_redis):
        mock_redis.get.return_value = "https://example.com"

        resp = client.get("/abc", follow_redirects=False)

        assert resp.status_code == 301
        assert resp.headers["location"] == "https://example.com"
        mock_pool.fetchrow.assert_not_called()

    def test_unknown_short_code_returns_404(self, client, mock_pool, mock_redis):
        mock_redis.get.return_value = None
        mock_pool.fetchrow.return_value = None

        resp = client.get("/nonexistent", follow_redirects=False)

        assert resp.status_code == 404


class TestListUrls:
    def test_empty_list(self, client, mock_pool):
        mock_pool.fetch.return_value = []
        resp = client.get("/api/urls")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_urls(self, client, mock_pool):
        mock_pool.fetch.return_value = [
            make_row(
                short_code="abc",
                full_url="https://example.com/",
                created_at=NOW,
                click_count=5,
            )
        ]
        resp = client.get("/api/urls")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["short_code"] == "abc"
        assert data[0]["click_count"] == 5


class TestStats:
    def test_not_found_returns_404(self, client, mock_pool):
        mock_pool.fetchrow.return_value = None
        resp = client.get("/api/stats/xyz")
        assert resp.status_code == 404

    def test_returns_stats(self, client, mock_pool):
        mock_pool.fetchrow.return_value = make_row(
            short_code="abc",
            full_url="https://example.com/",
            created_at=NOW,
        )
        mock_pool.fetchval.return_value = 42
        mock_pool.fetch.return_value = []

        resp = client.get("/api/stats/abc")

        assert resp.status_code == 200
        data = resp.json()
        assert data["short_code"] == "abc"
        assert data["total_clicks"] == 42
