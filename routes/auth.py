from fastapi import APIRouter, Depends, Body, HTTPException, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional

from controllers import auth_controller
from models.user import UserCreate, UserUpdate
from utils.auth import get_current_user

router = APIRouter()

@router.post("/register")
async def register(user_data: UserCreate):
    """
    Register a new user
    """
    return await auth_controller.register_user(user_data)

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login to get access token
    """
    return await auth_controller.login_user(form_data)

@router.get("/me")
async def get_current_user_profile(current_user = Depends(get_current_user)):
    """
    Get current user profile
    """
    return {"success": True, "data": current_user}

@router.put("/me")
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user = Depends(get_current_user)
):
    """
    Update current user profile
    """
    user_id = current_user["_id"]
    return await auth_controller.update_user_profile(user_id, user_data.model_dump(exclude_unset=True))

@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str):
    """
    Get user profile by ID
    """
    return await auth_controller.get_user_profile(user_id)

@router.get("/profile/username/{username}")
async def get_user_profile_by_username(username: str):
    """
    Get user profile by username
    """
    return await auth_controller.get_user_by_username(username)