import uuid
from fastapi import Request, Response, Depends
from utils.auth import get_current_user_optional

async def get_user_id(
    request: Request, 
    response: Response,
    current_user = Depends(get_current_user_optional)
):
    # If user is authenticated, use their ID
    if current_user:
        return current_user["_id"]
    
    # Otherwise use cookie-based tracking
    user_id = request.cookies.get("userId")
    
    if not user_id:
        user_id = str(uuid.uuid4())
        # Set cookie that expires in 1 year
        response.set_cookie(
            key="userId",
            value=user_id,
            max_age=365 * 24 * 60 * 60,  # 1 year
            httponly=True,
            samesite="strict"
        )
    
    return user_id