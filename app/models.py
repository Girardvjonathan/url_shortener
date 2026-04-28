from datetime import datetime

from pydantic import BaseModel, HttpUrl


class CreateURLRequest(BaseModel):
    """Request body for creating a new short URL."""
    full_url: HttpUrl


class CreateURLResponse(BaseModel):
    """Response body after creating/looking up a short URL."""
    short_url: str
    short_code: str
    full_url: str
    created_at: datetime
    is_new: bool  # True if newly created, False if deduplicated


class URLItem(BaseModel):
    """A single URL entry with its click count."""
    short_code: str
    short_url: str
    full_url: str
    click_count: int
    created_at: datetime


class URLStats(BaseModel):
    """Detailed statistics for a specific short URL."""
    short_code: str
    full_url: str
    total_clicks: int
    created_at: datetime
    recent_clicks: list[dict]
