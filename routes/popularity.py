from fastapi import APIRouter, Depends, Query, Path, Request
from typing import Optional

from controllers import popularity_controller
from middleware.auth_required import require_auth
from middleware.user_tracker import get_user_id
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/movies")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_popular_movies(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    period: str = Query("week", description="Time period: day, week, month, year, all"),
    current_user = Depends(require_auth)
):
    """
    Get popular movies based on view count
    """
    return await popularity_controller.get_popular_movies(limit, period)

@router.get("/shows")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_popular_shows(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    period: str = Query("week", description="Time period: day, week, month, year, all"),
    current_user = Depends(require_auth)
):
    """
    Get popular shows based on view count
    """
    return await popularity_controller.get_popular_shows(limit, period)

@router.post("/track/{content_type}/{content_id}")
@limiter.limit("60/minute")
async def track_content_view(
    request: Request,
    content_type: str = Path(..., description="Type of content: movie or show"),
    content_id: str = Path(..., description="ID of the content to track"),
    current_user = Depends(require_auth)
):
    """
    Track a view for a specific content item
    """
    user_id = current_user["_id"]
    return await popularity_controller.track_content_view(content_id, content_type, user_id) 