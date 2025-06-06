from fastapi import APIRouter, Depends, Body, HTTPException, Response, Cookie, Request
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional

from controllers import auth_controller
from models.user import UserCreate, UserUpdate
from utils.auth import get_current_user
from middleware.auth_required import require_auth, allow_user_or_admin
from middleware.api_auth import get_user_or_admin
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_AUTH

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

class TurnstileLoginData:
    def __init__(self, username: str, password: str, turnstile_token: str):
        self.username = username
        self.password = password
        self.turnstile_token = turnstile_token

@router.post("/register")
@limiter.limit(RATE_LIMIT_AUTH)
async def register(request: Request, user_data: UserCreate):
    """
    Register a new user with Turnstile verification
    """
    return await auth_controller.register_user(user_data, request)

@router.post("/login")
@limiter.limit(RATE_LIMIT_AUTH)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login to get access token
    """
    return await auth_controller.login_user(form_data)

@router.post("/login-with-turnstile")
@limiter.limit(RATE_LIMIT_AUTH)
async def login_with_turnstile(
    request: Request, 
    username: str = Body(...), 
    password: str = Body(...), 
    turnstile_token: str = Body(...)
):
    """
    Login with Turnstile verification to get access token
    """
    return await auth_controller.login_with_turnstile(username, password, turnstile_token, request)

@router.get("/me")
@limiter.limit(RATE_LIMIT_AUTH)
async def get_current_user_profile(request: Request):
    """
    Get current user profile
    """
    # Get user from request directly using the middleware
    current_user = await get_user_or_admin(request)
    return {"success": True, "data": current_user}

@router.put("/me")
@limiter.limit(RATE_LIMIT_AUTH)
async def update_current_user_profile(
    request: Request,
    user_data: UserUpdate
):
    """
    Update current user profile
    """
    current_user = await get_user_or_admin(request)
    user_id = current_user["_id"]
    return await auth_controller.update_user_profile(user_id, user_data.model_dump(exclude_unset=True))

@router.get("/profile/{user_id}")
@limiter.limit(RATE_LIMIT_AUTH)
async def get_user_profile(request: Request, user_id: str):
    """
    Get user profile by ID
    """
    # Verify that the user is authenticated, but don't require specific user rights
    await get_user_or_admin(request)
    return await auth_controller.get_user_profile(user_id)

@router.get("/profile/username/{username}")
@limiter.limit(RATE_LIMIT_AUTH)
async def get_user_profile_by_username(request: Request, username: str):
    """
    Get user profile by username
    """
    # Verify that the user is authenticated, but don't require specific user rights
    await get_user_or_admin(request)
    return await auth_controller.get_user_by_username(username)
