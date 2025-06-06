from fastapi import APIRouter, Depends, Query, Path, Cookie, Response, Request
from typing import Optional
import logging

from controllers import show_controller
from controllers.comment_controller import get_comments
from middleware.user_tracker import get_user_id
from utils.auth import get_current_user_optional
from middleware.auth_required import require_auth, allow_user_or_admin
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_all_shows(
    request: Request,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get all shows with optional filtering and pagination
    """
    return await show_controller.get_all_shows(tag, search, limit, page)

@router.get("/featured")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_featured_shows(
    request: Request,
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get featured shows
    """
    return await show_controller.get_featured_shows()

@router.get("/{show_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_show_by_id(
    request: Request,
    show_id: str = Path(..., description="The ID of the show to get"),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get a show by ID with all seasons but not all episodes
    """
    return await show_controller.get_show_by_id(show_id, user_id)

@router.get("/{show_id}/season/{season_id}/episodes")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_season_episodes(
    request: Request,
    show_id: str = Path(..., description="The ID of the show"),
    season_id: str = Path(..., description="The ID of the season"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get paginated episodes for a specific season
    """
    return await show_controller.get_season_episodes(show_id, season_id, page, limit, user_id)

@router.get("/episode/{episode_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_episode_by_id(
    request: Request,
    episode_id: str = Path(..., description="The ID of the episode to get"),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get an episode by ID
    """
    return await show_controller.get_episode_by_id(episode_id, user_id)

@router.post("/episode/{episode_id}/watch")
@limiter.limit("30/minute")
async def update_episode_watch_status(
    request: Request,
    episode_id: str = Path(..., description="The ID of the episode to update"),
    progress: float = Query(0, ge=0, le=100),
    completed: bool = False,
    current_user = Depends(allow_user_or_admin),
    user_id: str = Depends(get_user_id)
):
    """
    Update episode watch status
    """
    # Use authenticated user ID
    actual_user_id = current_user["_id"]
    return await show_controller.update_episode_watch_status(episode_id, actual_user_id, progress, completed)


@router.get("/{show_id}/season/{season_id}/all-episodes")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_all_season_episodes(
    request: Request,
    show_id: str = Path(..., description="The ID of the show"),
    season_id: str = Path(..., description="The ID of the season"),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get all episodes for a specific season without pagination
    """
    return await show_controller.get_all_season_episodes(show_id, season_id, user_id)

@router.get("/{show_id}/comments")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_show_comments(
    request: Request,
    show_id: str = Path(..., description="The ID of the show to get comments for"),
    parent_id: Optional[str] = Query(None, description="ID of parent comment to get replies"),
    limit: int = Query(50, description="Number of comments to return"),
    skip: int = Query(0, description="Number of comments to skip"),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get comments for a show
    """
    return await get_comments(show_id, "show", parent_id, limit, skip)
