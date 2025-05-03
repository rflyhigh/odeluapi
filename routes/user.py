from fastapi import APIRouter, Depends, Query, Path, Cookie, Response, Request
import logging

from controllers import user_controller
from middleware.user_tracker import get_user_id
from utils.auth import get_current_user, get_current_user_optional
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
async def get_watch_history(request: Request, current_user = Depends(get_current_user)):
    """
    Get user's watch history
    """
    user_id = current_user["_id"]
    return await user_controller.get_watch_history(user_id)

@router.get("/continue-watching")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_continue_watching(request: Request, current_user = Depends(get_current_user)):
    """
    Get user's continue watching list
    """
    user_id = current_user["_id"]
    return await user_controller.get_continue_watching(user_id)

@router.get("/me")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_user_profile(request: Request, current_user = Depends(get_current_user_optional)):
    """
    Get current user profile if authenticated
    """
    if current_user:
        return await user_controller.get_user_by_token(current_user)
    else:
        return {"success": False, "message": "Not authenticated"}
