from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Body, status
from typing import Optional, Union

from controllers.comment_controller import (
    create_comment, 
    get_comments, 
    get_comment_by_id, 
    update_comment, 
    delete_comment,
    get_comment_tree,
    get_user_comments
)
from models.comment import CommentCreate
from utils.auth import get_current_user
from middleware.auth_required import require_auth
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT, COMMENT_CACHE_TTL
from database import get_cache, set_cache

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# Create a new comment
@router.post("/")
@limiter.limit("20/minute")
async def post_comment(
    request: Request,
    comment_data: CommentCreate,
    current_user: dict = Depends(require_auth)
):
    return await create_comment(comment_data, current_user)

# Get comments for a movie or show
@router.get("/content/{content_type}/{content_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def list_comments(
    request: Request,
    content_type: str = Path(..., description="Type of content: movie or show"),
    content_id: str = Path(..., description="ID of the content to get comments for"),
    parent_id: Optional[str] = Query(None, description="ID of parent comment to get replies"),
    limit: int = Query(50, description="Number of comments to return"),
    skip: int = Query(0, description="Number of comments to skip"),
    refresh: Union[bool, None] = Query(False, description="Set to true to bypass cache and get fresh data"),
    current_user = Depends(require_auth)
):
    # Try to get from cache first (unless refresh is true)
    if not refresh:
        cache_key = f"comments:{content_type}:{content_id}:{parent_id}:{limit}:{skip}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
    # If not in cache or refresh requested, fetch from database
    result = await get_comments(content_id, content_type, parent_id, limit, skip)
    
    # Store in cache only if not a refresh request
    if not refresh:
        await set_cache(cache_key, result, ttl=COMMENT_CACHE_TTL)
    
    return result

# Get comments by user ID - moved up to avoid conflict with /{comment_id}
@router.get("/user/{user_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_comments_by_user(
    request: Request,
    user_id: str = Path(..., description="ID of the user to get comments for"),
    limit: int = Query(50, description="Number of comments to return"),
    skip: int = Query(0, description="Number of comments to skip"),
    refresh: Union[bool, None] = Query(False, description="Set to true to bypass cache and get fresh data"),
    current_user = Depends(require_auth)
):
    """
    Get all comments made by a specific user
    """
    # Try to get from cache first (unless refresh is true)
    if not refresh:
        cache_key = f"user_comments:{user_id}:{limit}:{skip}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
    # If not in cache or refresh requested, fetch from database
    result = await get_user_comments(user_id, limit, skip)
    
    # Store in cache only if not a refresh request
    if not refresh:
        await set_cache(cache_key, result, ttl=COMMENT_CACHE_TTL)
    
    return result

# Get a specific comment
@router.get("/{comment_id}")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_comment(
    request: Request,
    comment_id: str = Path(..., description="ID of the comment to get"),
    refresh: Union[bool, None] = Query(False, description="Set to true to bypass cache and get fresh data"),
    current_user = Depends(require_auth)
):
    # Try to get from cache first (unless refresh is true)
    if not refresh:
        cache_key = f"comment:{comment_id}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
    # If not in cache or refresh requested, fetch from database
    result = await get_comment_by_id(comment_id)
    
    # Store in cache only if not a refresh request
    if not refresh:
        await set_cache(cache_key, result, ttl=COMMENT_CACHE_TTL)
    
    return result

# Get a comment tree (comment with all nested replies)
@router.get("/{comment_id}/tree")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_nested_comment(
    request: Request,
    comment_id: str = Path(..., description="ID of the comment to get with all its replies"),
    refresh: Union[bool, None] = Query(False, description="Set to true to bypass cache and get fresh data"),
    current_user = Depends(require_auth)
):
    # Try to get from cache first (unless refresh is true)
    if not refresh:
        cache_key = f"comment_tree:{comment_id}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
    # If not in cache or refresh requested, fetch from database
    result = await get_comment_tree(comment_id)
    
    # Store in cache only if not a refresh request
    if not refresh:
        await set_cache(cache_key, result, ttl=COMMENT_CACHE_TTL)
    
    return result

# Update a comment
@router.put("/{comment_id}")
@limiter.limit("20/minute")
async def edit_comment(
    request: Request,
    comment_id: str = Path(..., description="ID of the comment to update"),
    content_data: dict = Body(...),  # Change to accept a JSON body
    current_user: dict = Depends(require_auth)
):
    # Extract content from the JSON body
    content = content_data.get("content")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'content' is required"
        )
    return await update_comment(comment_id, content, current_user)

# Delete a comment
@router.delete("/{comment_id}")
@limiter.limit("20/minute")
async def remove_comment(
    request: Request,
    comment_id: str = Path(..., description="ID of the comment to delete"),
    current_user: dict = Depends(require_auth)
):
    return await delete_comment(comment_id, current_user) 