from fastapi import APIRouter, Depends, Body, HTTPException, Response, Cookie, Request
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional
from fastapi.responses import JSONResponse

from controllers import auth_controller
from models.user import UserCreate, UserUpdate
from utils.auth import get_current_user
from middleware.auth_required import require_auth
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_AUTH

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.post("/register")
@limiter.limit(RATE_LIMIT_AUTH)
async def register(request: Request, user_data: UserCreate):
    """
    Register a new user
    """
    return await auth_controller.register_user(user_data)

@router.post("/login")
@limiter.limit(RATE_LIMIT_AUTH)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login to get access token
    """
    try:
        return await auth_controller.login_user(form_data)
    except HTTPException as e:
        # Ensure we return proper error format even if HTTPException is raised
        if e.status_code == 401:
            return JSONResponse(
                status_code=e.status_code,
                content={"success": False, "message": "Invalid email or password. Please try again."}
            )
        # For other exceptions, just pass through
        raise

@router.get("/me")
@limiter.limit(RATE_LIMIT_AUTH)
async def get_current_user_profile(request: Request, current_user = Depends(require_auth)):
    """
    Get current user profile
    """
    return {"success": True, "data": current_user}

@router.put("/me")
@limiter.limit(RATE_LIMIT_AUTH)
async def update_current_user_profile(
    request: Request,
    user_data: UserUpdate,
    current_user = Depends(require_auth)
):
    """
    Update current user profile
    """
    user_id = current_user["_id"]
    return await auth_controller.update_user_profile(user_id, user_data.model_dump(exclude_unset=True))

@router.get("/profile/{user_id}")
@limiter.limit(RATE_LIMIT_AUTH)
async def get_user_profile(request: Request, user_id: str, current_user = Depends(require_auth)):
    """
    Get user profile by ID
    """
    return await auth_controller.get_user_profile(user_id)

@router.get("/profile/username/{username}")
@limiter.limit(RATE_LIMIT_AUTH)
async def get_user_profile_by_username(request: Request, username: str, current_user = Depends(require_auth)):
    """
    Get user profile by username
    """
    return await auth_controller.get_user_by_username(username)
