import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.cache import create_redis
from app.config import settings
from app.database import create_pool, init_db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of database and cache connections."""
    # Startup
    logger.info("Connecting to PostgreSQL...")
    app.state.pool = await create_pool(settings.database_url)
    await init_db(app.state.pool)
    logger.info("PostgreSQL connected, tables initialized.")

    logger.info("Connecting to Redis...")
    app.state.redis = await create_redis(settings.redis_url)
    logger.info("Redis connected.")

    yield

    # Shutdown
    logger.info("Closing connections...")
    await app.state.redis.close()
    await app.state.pool.close()
    logger.info("Connections closed.")


app = FastAPI(
    title="URL Shortener",
    description="An internal URL shortener with Redis caching",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Import and include routes (deferred to avoid circular imports)
from app.routes import api, pages  # noqa: E402

app.include_router(api.router)
app.include_router(pages.router)
