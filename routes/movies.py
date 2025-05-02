from fastapi import APIRouter, Depends, Query, Path, Cookie, Response
from typing import Optional
import logging

from controllers import movie_controller
from middleware.user_tracker import get_user_id
from utils.auth import get_current_user_optional

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def get_all_movies(
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user_id: str = Depends(get_user_id)
):
    """
    Get all movies with optional filtering and pagination
    """
    return await movie_controller.get_all_movies(tag, search, limit, page)

@router.get("/featured")
async def get_featured_movies(user_id: str = Depends(get_user_id)):
    """
    Get featured movies
    """
    return await movie_controller.get_featured_movies()

@router.get("/{movie_id}")
async def get_movie_by_id(
    movie_id: str = Path(..., description="The ID of the movie to get"),
    user_id: str = Depends(get_user_id)
):
    """
    Get a movie by ID
    """
    return await movie_controller.get_movie_by_id(movie_id, user_id)

@router.post("/{movie_id}/watch")
async def update_watch_status(
    movie_id: str = Path(..., description="The ID of the movie to update"),
    progress: float = Query(0, ge=0, le=100),
    completed: bool = False,
    current_user = Depends(get_current_user_optional),
    user_id: str = Depends(get_user_id)
):
    """
    Update movie watch status
    """
    # Use authenticated user ID if available, otherwise use cookie ID
    actual_user_id = current_user["_id"] if current_user else user_id
    return await movie_controller.update_watch_status(movie_id, actual_user_id, progress, completed)