from __future__ import annotations

import logging

import aioboto3

logger = logging.getLogger(__name__)


def create_dynamo_session(region: str, access_key_id: str | None, secret_access_key: str | None):
    return aioboto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )


async def open_dynamo_table(session, table_name: str):
    """Enter the DynamoDB resource context once and return (cm, table) for reuse."""
    cm = session.resource("dynamodb")
    dynamo = await cm.__aenter__()
    table = await dynamo.Table(table_name)
    return cm, table


async def get_dynamo_url(table, short_code: str) -> str | None:
    """Look up a short code in DynamoDB. Returns None on miss or error."""
    try:
        resp = await table.get_item(Key={"short_code": short_code})
        item = resp.get("Item")
        return item["full_url"] if item else None
    except Exception as e:
        logger.warning("DynamoDB GET failed for %s: %s", short_code, e)
        return None


async def put_dynamo_url(table, short_code: str, full_url: str) -> None:
    """Write a short_code -> full_url mapping to DynamoDB. Silently fails on error."""
    try:
        await table.put_item(Item={"short_code": short_code, "full_url": full_url})
    except Exception as e:
        logger.warning("DynamoDB PUT failed for %s: %s", short_code, e)
