from fastapi import APIRouter, Request, Query, Depends
from typing import Optional

from controllers import search_controller
from middleware.auth_required import require_auth
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/suggestions")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_search_suggestions(
    request: Request, 
    q: str = Query(..., description="Search query string"),
    limit: Optional[int] = Query(10, ge=1, le=20, description="Maximum number of results to return"),
    current_user = Depends(require_auth)
):
    """
    Get search suggestions for movies, shows, and users based on a query string.
    This endpoint returns quick suggestions for autocomplete.
    """
    return await search_controller.get_search_suggestions(q, limit) 