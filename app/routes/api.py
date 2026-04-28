import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from app.cache import cache_url
from app.config import settings
from app.models import CreateURLRequest, CreateURLResponse, URLItem, URLStats
from app.shortener import base62_encode, generate_unique_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])

MAX_RETRIES = 5


@router.post("/shorten", response_model=CreateURLResponse)
async def shorten_url(request: Request, body: CreateURLRequest):
    """Create a new short URL or return existing one if the URL was already shortened."""
    pool = request.app.state.pool
    redis = request.app.state.redis
    full_url = str(body.full_url)

    # Step 1: Check if this URL already exists (deduplication)
    existing = await pool.fetchrow(
        "SELECT id, short_code, full_url, created_at FROM urls WHERE full_url = $1",
        full_url,
    )
    if existing:
        short_code = existing["short_code"]
        return CreateURLResponse(
            short_url=f"{settings.base_url}/{short_code}",
            short_code=short_code,
            full_url=full_url,
            created_at=existing["created_at"],
            is_new=False,
        )

    # Step 2: Generate a new unique ID and base62-encode it
    for attempt in range(MAX_RETRIES):
        unique_id = generate_unique_id()
        short_code = base62_encode(unique_id)

        try:
            row = await pool.fetchrow(
                """INSERT INTO urls (id, short_code, full_url)
                   VALUES ($1, $2, $3)
                   RETURNING created_at""",
                unique_id,
                short_code,
                full_url,
            )

            # Cache the new mapping
            asyncio.create_task(cache_url(redis, short_code, full_url))

            return CreateURLResponse(
                short_url=f"{settings.base_url}/{short_code}",
                short_code=short_code,
                full_url=full_url,
                created_at=row["created_at"],
                is_new=True,
            )
        except Exception as e:
            # Unique constraint violation — retry with a new ID
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info(
                    "Collision on ID %d (attempt %d/%d), retrying...",
                    unique_id,
                    attempt + 1,
                    MAX_RETRIES,
                )
                continue
            raise

    raise HTTPException(
        status_code=503,
        detail="Failed to generate unique short code after multiple attempts",
    )


@router.get("/urls", response_model=list[URLItem])
async def list_urls(request: Request):
    """List recent URLs with their click counts."""
    pool = request.app.state.pool

    rows = await pool.fetch(
        """SELECT u.short_code, u.full_url, u.created_at,
                  COUNT(c.id) AS click_count
           FROM urls u
           LEFT JOIN clicks c ON u.short_code = c.short_code
           GROUP BY u.id
           ORDER BY u.created_at DESC
           LIMIT 50"""
    )

    return [
        URLItem(
            short_code=row["short_code"],
            short_url=f"{settings.base_url}/{row['short_code']}",
            full_url=row["full_url"],
            click_count=row["click_count"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.get("/stats/{short_code}", response_model=URLStats)
async def get_stats(request: Request, short_code: str):
    """Get detailed stats for a specific short URL."""
    pool = request.app.state.pool

    url_row = await pool.fetchrow(
        "SELECT short_code, full_url, created_at FROM urls WHERE short_code = $1",
        short_code,
    )
    if not url_row:
        raise HTTPException(status_code=404, detail="Short URL not found")

    click_count = await pool.fetchval(
        "SELECT COUNT(*) FROM clicks WHERE short_code = $1",
        short_code,
    )

    recent = await pool.fetch(
        """SELECT clicked_at, ip_address::text, user_agent, referrer
           FROM clicks
           WHERE short_code = $1
           ORDER BY clicked_at DESC
           LIMIT 10""",
        short_code,
    )

    return URLStats(
        short_code=url_row["short_code"],
        full_url=url_row["full_url"],
        total_clicks=click_count,
        created_at=url_row["created_at"],
        recent_clicks=[dict(r) for r in recent],
    )
