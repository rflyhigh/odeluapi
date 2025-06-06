from fastapi import Depends, HTTPException, status, Request
from utils.auth import get_current_user
from middleware.api_auth import get_user_or_admin

async def require_auth(current_user = Depends(get_current_user)):
    """
    Middleware to require authentication for all endpoints.
    This simply uses the get_current_user dependency which will raise
    an HTTPException if the user is not authenticated.
    """
    return current_user 

async def allow_user_or_admin(request: Request):
    """
    Middleware that allows access if either:
    1. The request has a valid JWT token (user authentication)
    2. The request has a valid API key (admin authentication)
    
    This is used for endpoints that should be accessible by both users and admins.
    """
    return await get_user_or_admin(request) 