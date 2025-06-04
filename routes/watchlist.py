from fastapi import APIRouter, Depends, Path, Query, Request
from typing import Optional

from controllers import watchlist_controller
from utils.auth import get_current_user
from middleware.auth_required import require_auth
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_watchlist(request: Request, current_user = Depends(require_auth)):
    """
    Get current user's watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.get_watchlist(user_id)

@router.post("/add")
@limiter.limit("30/minute")
async def add_to_watchlist(
    request: Request,
    content_type: str = Query(..., description="Type of content: 'movie' or 'show'"),
    content_id: str = Query(..., description="ID of the content to add"),
    current_user = Depends(require_auth)
):
    """
    Add item to watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.add_to_watchlist(user_id, content_type, content_id)

@router.delete("/remove")
@limiter.limit("30/minute")
async def remove_from_watchlist(
    request: Request,
    content_type: str = Query(..., description="Type of content: 'movie' or 'show'"),
    content_id: str = Query(..., description="ID of the content to remove"),
    current_user = Depends(require_auth)
):
    """
    Remove item from watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.remove_from_watchlist(user_id, content_type, content_id)

@router.get("/check")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def check_watchlist(
    request: Request,
    content_type: str = Query(..., description="Type of content: 'movie' or 'show'"),
    content_id: str = Query(..., description="ID of the content to check"),
    current_user = Depends(require_auth)
):
    """
    Check if item is in watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.is_in_watchlist(user_id, content_type, content_id)

@router.get("/user/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_user_watchlist(
    request: Request,
    user_id: str = Path(..., description="ID of the user to get watchlist for"),
    current_user = Depends(require_auth)
):
    """
    Get watchlist for a specific user (for public profile viewing)
    """
    return await watchlist_controller.get_user_watchlist(user_id)
