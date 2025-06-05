from fastapi import APIRouter, Depends, Request
from controllers import utils_controller
from middleware.auth_required import require_auth
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/timezone")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_timezone_info(request: Request):
    """
    Get timezone information including:
    - Current UTC time
    - List of all available timezones
    - Common timezones with their current offsets from UTC
    
    This endpoint can be used by the frontend to:
    1. Show the current server time (UTC)
    2. Display times in the user's local timezone
    3. Allow users to select their preferred timezone
    """
    return await utils_controller.get_timezone_info()

@router.get("/server-time")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_server_time(request: Request):
    """
    Get the current server time in UTC.
    Simple endpoint that just returns the current UTC time.
    """
    from datetime import datetime
    import pytz
    
    current_utc = datetime.now(pytz.UTC)
    return {
        "success": True,
        "data": {
            "utc": current_utc.strftime("%Y-%m-%dT%H:%M:%S"),
            "timestamp": int(current_utc.timestamp())
        }
    } 