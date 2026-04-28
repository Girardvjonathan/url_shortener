import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.cache import cache_url, get_cached_url

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def home(request: Request):
    """Render the main page with the URL shortening form and recent URLs."""
    pool = request.app.state.pool

    rows = await pool.fetch(
        """SELECT u.short_code, u.full_url, u.created_at,
                  COUNT(c.id) AS click_count
           FROM urls u
           LEFT JOIN clicks c ON u.short_code = c.short_code
           GROUP BY u.id
           ORDER BY u.created_at DESC
           LIMIT 20"""
    )

    return templates.TemplateResponse(
        request,
        "index.html",
        {"urls": rows},
    )


@router.get("/{short_code}")
async def redirect_to_url(request: Request, short_code: str):
    """Look up the short code and redirect to the full URL."""
    pool = request.app.state.pool
    redis = request.app.state.redis

    # Step 1: Check Redis cache
    full_url = await get_cached_url(redis, short_code)

    # Step 2: Cache miss — query PostgreSQL
    if not full_url:
        row = await pool.fetchrow(
            "SELECT full_url FROM urls WHERE short_code = $1",
            short_code,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Short URL not found")

        full_url = row["full_url"]

        # Populate cache for next time
        asyncio.create_task(cache_url(redis, short_code, full_url))

    # Step 3: Log the click asynchronously (fire-and-forget)
    asyncio.create_task(
        _log_click(pool, short_code, request)
    )

    # Step 4: Redirect
    return RedirectResponse(url=full_url, status_code=301)


async def _log_click(pool, short_code: str, request: Request) -> None:
    """Log a click event to the database. Runs as a background task."""
    try:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        referrer = request.headers.get("referer")

        await pool.execute(
            """INSERT INTO clicks (short_code, ip_address, user_agent, referrer)
               VALUES ($1, $2::inet, $3, $4)""",
            short_code,
            ip_address,
            user_agent,
            referrer,
        )
    except Exception as e:
        logger.error("Failed to log click for %s: %s", short_code, e)
