from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dynamo import get_dynamo_url, put_dynamo_url

TABLE = "test_table"


def make_dynamo_session(table_mock) -> MagicMock:
    """Return a fake aioboto3 session whose resource() yields table_mock."""
    resource = AsyncMock()
    resource.Table.return_value = table_mock

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resource)
    cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.resource.return_value = cm
    return session


class TestGetDynamoUrl:
    async def test_hit_returns_full_url(self):
        table = AsyncMock()
        table.get_item.return_value = {"Item": {"short_code": "abc", "full_url": "https://example.com"}}
        session = make_dynamo_session(table)

        result = await get_dynamo_url(session, TABLE, "abc")

        assert result == "https://example.com"
        table.get_item.assert_called_once_with(Key={"short_code": "abc"})

    async def test_miss_returns_none(self):
        table = AsyncMock()
        table.get_item.return_value = {}
        session = make_dynamo_session(table)

        result = await get_dynamo_url(session, TABLE, "xyz")

        assert result is None

    async def test_aws_error_returns_none_gracefully(self):
        table = AsyncMock()
        table.get_item.side_effect = Exception("AWS connection error")
        session = make_dynamo_session(table)

        result = await get_dynamo_url(session, TABLE, "abc")

        assert result is None


class TestPutDynamoUrl:
    async def test_put_item_called_with_correct_args(self):
        table = AsyncMock()
        session = make_dynamo_session(table)

        await put_dynamo_url(session, TABLE, "abc", "https://example.com")

        table.put_item.assert_called_once_with(
            Item={"short_code": "abc", "full_url": "https://example.com"}
        )

    async def test_aws_error_is_silenced(self):
        table = AsyncMock()
        table.put_item.side_effect = Exception("AWS connection error")
        session = make_dynamo_session(table)

        await put_dynamo_url(session, TABLE, "abc", "https://example.com")  # must not raise
