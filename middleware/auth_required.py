from fastapi import Depends, HTTPException, status
from utils.auth import get_current_user

async def require_auth(current_user = Depends(get_current_user)):
    """
    Middleware to require authentication for all endpoints.
    This simply uses the get_current_user dependency which will raise
    an HTTPException if the user is not authenticated.
    It preserves the original error message from the get_current_user function.
    """
    return current_user 