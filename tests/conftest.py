from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


class FakeRow(dict):
    """Dict that behaves like an asyncpg Record for [] access."""
    pass


def make_row(**kwargs) -> FakeRow:
    return FakeRow(kwargs)


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.fetchrow.return_value = None
    pool.fetch.return_value = []
    pool.fetchval.return_value = 0
    pool.execute.return_value = None
    return pool


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get.return_value = None
    return r


@pytest.fixture
def mock_dynamo_session():
    return MagicMock()


@pytest.fixture
def client(mock_pool, mock_redis, mock_dynamo_session):
    from app.main import app

    async def fake_create_pool(*a, **kw):
        return mock_pool

    async def fake_create_redis(*a, **kw):
        return mock_redis

    async def fake_init_db(pool):
        pass

    def fake_create_dynamo_session(*a, **kw):
        return mock_dynamo_session

    with (
        patch("app.main.create_pool", fake_create_pool),
        patch("app.main.create_redis", fake_create_redis),
        patch("app.main.init_db", fake_init_db),
        patch("app.main.create_dynamo_session", fake_create_dynamo_session),
    ):
        with TestClient(app) as c:
            yield c
