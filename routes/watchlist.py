from fastapi import APIRouter, Depends, Path, Query
from typing import Optional

from controllers import watchlist_controller
from utils.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_watchlist(current_user = Depends(get_current_user)):
    """
    Get current user's watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.get_watchlist(user_id)

@router.post("/add")
async def add_to_watchlist(
    content_type: str = Query(..., description="Type of content: 'movie' or 'show'"),
    content_id: str = Query(..., description="ID of the content to add"),
    current_user = Depends(get_current_user)
):
    """
    Add item to watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.add_to_watchlist(user_id, content_type, content_id)

@router.delete("/remove")
async def remove_from_watchlist(
    content_type: str = Query(..., description="Type of content: 'movie' or 'show'"),
    content_id: str = Query(..., description="ID of the content to remove"),
    current_user = Depends(get_current_user)
):
    """
    Remove item from watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.remove_from_watchlist(user_id, content_type, content_id)

@router.get("/check")
async def check_watchlist(
    content_type: str = Query(..., description="Type of content: 'movie' or 'show'"),
    content_id: str = Query(..., description="ID of the content to check"),
    current_user = Depends(get_current_user)
):
    """
    Check if item is in watchlist
    """
    user_id = current_user["_id"]
    return await watchlist_controller.is_in_watchlist(user_id, content_type, content_id)