from fastapi import APIRouter, Depends, Query, Path, Cookie, Response
from typing import Optional
import logging

from controllers import show_controller
from middleware.user_tracker import get_user_id
from utils.auth import get_current_user_optional

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def get_all_shows(
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user_id: str = Depends(get_user_id)
):
    """
    Get all shows with optional filtering and pagination
    """
    return await show_controller.get_all_shows(tag, search, limit, page)

@router.get("/featured")
async def get_featured_shows(user_id: str = Depends(get_user_id)):
    """
    Get featured shows
    """
    return await show_controller.get_featured_shows()

@router.get("/{show_id}")
async def get_show_by_id(
    show_id: str = Path(..., description="The ID of the show to get"),
    user_id: str = Depends(get_user_id)
):
    """
    Get a show by ID with all seasons and episodes
    """
    return await show_controller.get_show_by_id(show_id, user_id)

@router.get("/episode/{episode_id}")
async def get_episode_by_id(
    episode_id: str = Path(..., description="The ID of the episode to get"),
    user_id: str = Depends(get_user_id)
):
    """
    Get an episode by ID
    """
    return await show_controller.get_episode_by_id(episode_id, user_id)

@router.post("/episode/{episode_id}/watch")
async def update_episode_watch_status(
    episode_id: str = Path(..., description="The ID of the episode to update"),
    progress: float = Query(0, ge=0, le=100),
    completed: bool = False,
    current_user = Depends(get_current_user_optional),
    user_id: str = Depends(get_user_id)
):
    """
    Update episode watch status
    """
    # Use authenticated user ID if available, otherwise use cookie ID
    actual_user_id = current_user["_id"] if current_user else user_id
    return await show_controller.update_episode_watch_status(episode_id, actual_user_id, progress, completed)