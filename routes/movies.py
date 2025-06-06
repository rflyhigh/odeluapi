from fastapi import APIRouter, Depends, Query, Path, Cookie, Response, Request
from typing import Optional
import logging

from controllers import movie_controller
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
async def get_all_movies(
    request: Request,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get all movies with optional filtering and pagination
    """
    return await movie_controller.get_all_movies(tag, search, limit, page)

@router.get("/featured")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_featured_movies(
    request: Request,
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get featured movies
    """
    return await movie_controller.get_featured_movies()

@router.get("/{movie_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_movie_by_id(
    request: Request,
    movie_id: str = Path(..., description="The ID of the movie to get"),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get a movie by ID
    """
    return await movie_controller.get_movie_by_id(movie_id, user_id)

@router.post("/{movie_id}/watch")
@limiter.limit("30/minute")
async def update_watch_status(
    request: Request,
    movie_id: str = Path(..., description="The ID of the movie to update"),
    progress: float = Query(0, ge=0, le=100),
    completed: bool = False,
    current_user = Depends(allow_user_or_admin),
    user_id: str = Depends(get_user_id)
):
    """
    Update movie watch status
    """
    # Use authenticated user ID
    actual_user_id = current_user["_id"]
    return await movie_controller.update_watch_status(movie_id, actual_user_id, progress, completed)

@router.get("/{movie_id}/comments")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_movie_comments(
    request: Request,
    movie_id: str = Path(..., description="The ID of the movie to get comments for"),
    parent_id: Optional[str] = Query(None, description="ID of parent comment to get replies"),
    limit: int = Query(50, description="Number of comments to return"),
    skip: int = Query(0, description="Number of comments to skip"),
    user_id: str = Depends(get_user_id),
    current_user = Depends(allow_user_or_admin)
):
    """
    Get comments for a movie
    """
    return await get_comments(movie_id, "movie", parent_id, limit, skip)
