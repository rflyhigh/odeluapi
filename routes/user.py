from fastapi import APIRouter, Depends, Query, Path, Cookie, Response, Request
import logging

from controllers import user_controller
from controllers.comment_controller import get_user_comments
from middleware.user_tracker import get_user_id
from utils.auth import get_current_user, get_current_user_optional
from middleware.auth_required import require_auth
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "OK"}

@router.get("/history")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_watch_history(
    request: Request, 
    current_user = Depends(require_auth)
):
    """
    Get user's watch history
    """
    user_id = current_user["_id"]
    return await user_controller.get_watch_history(user_id)

@router.get("/continue-watching")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_continue_watching(
    request: Request, 
    current_user = Depends(require_auth)
):
    """
    Get user's continue watching list
    """
    user_id = current_user["_id"]
    return await user_controller.get_continue_watching(user_id)


@router.get("/recently-added")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_recently_added_content(
    request: Request,
    limit: int = Query(5, ge=1, le=10),
    current_user = Depends(require_auth)
):
    """
    Get recently added content (movies and episodes)
    """
    return await user_controller.get_recently_added(limit)

@router.get("/me")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_user_profile(
    request: Request, 
    current_user = Depends(require_auth)
):
    """
    Get current user profile if authenticated
    """
    return await user_controller.get_user_by_token(current_user)

@router.delete("/history")
@limiter.limit("10/minute")
async def delete_user_watch_history(
    request: Request, 
    current_user = Depends(require_auth)
):
    """
    Delete user's watch history
    """
    user_id = current_user["_id"]
    return await user_controller.delete_watch_history(user_id)

@router.delete("/account")
@limiter.limit("5/minute")
async def delete_user_account(
    request: Request, 
    current_user = Depends(require_auth)
):
    """
    Delete user account and all associated data
    """
    user_id = current_user["_id"]
    return await user_controller.delete_account(user_id)

@router.get("/me/comments")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_my_comments(
    request: Request, 
    limit: int = Query(50, description="Number of comments to return"),
    skip: int = Query(0, description="Number of comments to skip"),
    current_user = Depends(require_auth)
):
    """
    Get the current user's comments
    """
    user_id = current_user["_id"]
    return await get_user_comments(user_id, limit, skip)
