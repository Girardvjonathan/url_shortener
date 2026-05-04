from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.cache import CACHE_TTL
from app.models import CreateURLRequest
from app.shortener import base62_encode, generate_unique_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])

MAX_RETRIES = 5

REDIS_KEY_PREFIX = "url:"


class BenchmarkLookupResult(BaseModel):
    short_code: str
    full_url: str | None
    redis_ms: float
    redis_error: str | None = None
    postgres_ms: float
    postgres_error: str | None = None
    dynamo_ms: float
    dynamo_error: str | None = None
    winner: str | None  # None if every store errored


class BenchmarkShortenResult(BaseModel):
    short_code: str | None
    full_url: str
    postgres_write_ms: float
    postgres_write_error: str | None = None
    dynamo_write_ms: float
    dynamo_write_error: str | None = None
    redis_write_ms: float
    redis_write_error: str | None = None


async def _write_postgres(pool, full_url: str) -> str:
    for _ in range(MAX_RETRIES):
        unique_id = generate_unique_id()
        short_code = base62_encode(unique_id)
        try:
            await pool.fetchrow(
                "INSERT INTO urls (id, short_code, full_url) VALUES ($1, $2, $3) RETURNING created_at",
                unique_id, short_code, full_url,
            )
            return short_code
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            raise
    raise RuntimeError("Failed to generate unique short code after multiple attempts")


@router.get("/lookup/{short_code}", response_model=BenchmarkLookupResult)
async def benchmark_lookup(request: Request, short_code: str):
    """Look up a short code in all three stores and return per-store latency + any errors."""
    pool = request.app.state.pool
    redis = request.app.state.redis
    dynamo_table = request.app.state.dynamo_table

    # Redis
    redis_url = redis_error = None
    t0 = time.perf_counter()
    try:
        redis_url = await redis.get(f"{REDIS_KEY_PREFIX}{short_code}")
    except Exception as e:
        redis_error = str(e)
    redis_ms = round((time.perf_counter() - t0) * 1000, 3)

    # Postgres
    pg_url = postgres_error = None
    t0 = time.perf_counter()
    try:
        row = await pool.fetchrow("SELECT full_url FROM urls WHERE short_code = $1", short_code)
        pg_url = row["full_url"] if row else None
    except Exception as e:
        postgres_error = str(e)
    postgres_ms = round((time.perf_counter() - t0) * 1000, 3)

    # DynamoDB
    dynamo_url = dynamo_error = None
    t0 = time.perf_counter()
    try:
        resp = await dynamo_table.get_item(Key={"short_code": short_code})
        item = resp.get("Item")
        dynamo_url = item["full_url"] if item else None
    except Exception as e:
        dynamo_error = str(e)
    dynamo_ms = round((time.perf_counter() - t0) * 1000, 3)

    full_url = redis_url or pg_url or dynamo_url

    non_errored = {
        k: v for k, v in
        {"redis": redis_ms, "postgres": postgres_ms, "dynamo": dynamo_ms}.items()
        if not {"redis": redis_error, "postgres": postgres_error, "dynamo": dynamo_error}[k]
    }
    winner = min(non_errored, key=non_errored.get) if non_errored else None

    return BenchmarkLookupResult(
        short_code=short_code,
        full_url=full_url,
        redis_ms=redis_ms,
        redis_error=redis_error,
        postgres_ms=postgres_ms,
        postgres_error=postgres_error,
        dynamo_ms=dynamo_ms,
        dynamo_error=dynamo_error,
        winner=winner,
    )


@router.post("/shorten", response_model=BenchmarkShortenResult)
async def benchmark_shorten(request: Request, body: CreateURLRequest):
    """Write a URL to all three stores and return per-store write latency + any errors."""
    pool = request.app.state.pool
    redis = request.app.state.redis
    dynamo_table = request.app.state.dynamo_table
    full_url = str(body.full_url)

    # Postgres (source of truth — generates the short_code)
    short_code = postgres_write_error = None
    t0 = time.perf_counter()
    try:
        short_code = await _write_postgres(pool, full_url)
    except Exception as e:
        postgres_write_error = str(e)
    postgres_write_ms = round((time.perf_counter() - t0) * 1000, 3)

    # DynamoDB
    dynamo_write_error = None
    t0 = time.perf_counter()
    if short_code:
        try:
            await dynamo_table.put_item(Item={"short_code": short_code, "full_url": full_url})
        except Exception as e:
            dynamo_write_error = str(e)
    else:
        dynamo_write_error = "skipped: no short_code from Postgres"
    dynamo_write_ms = round((time.perf_counter() - t0) * 1000, 3)

    # Redis
    redis_write_error = None
    t0 = time.perf_counter()
    if short_code:
        try:
            await redis.setex(f"{REDIS_KEY_PREFIX}{short_code}", CACHE_TTL, full_url)
        except Exception as e:
            redis_write_error = str(e)
    else:
        redis_write_error = "skipped: no short_code from Postgres"
    redis_write_ms = round((time.perf_counter() - t0) * 1000, 3)

    return BenchmarkShortenResult(
        short_code=short_code,
        full_url=full_url,
        postgres_write_ms=postgres_write_ms,
        postgres_write_error=postgres_write_error,
        dynamo_write_ms=dynamo_write_ms,
        dynamo_write_error=dynamo_write_error,
        redis_write_ms=redis_write_ms,
        redis_write_error=redis_write_error,
    )
