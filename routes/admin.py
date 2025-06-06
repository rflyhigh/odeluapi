# admin_router.py
from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, Request
from typing import Optional, Dict, Any, List
import logging

from controllers import admin_controller # Ensure this import is correct
from controllers.comment_controller import get_comments, delete_comment
from controllers import report_controller
from models.report import ReportUpdate
from middleware.api_auth import verify_api_key
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_ADMIN
from database import comment_collection, serialize_doc

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Apply API key authentication to all admin routes
router = APIRouter(
    dependencies=[Depends(verify_api_key)],
    tags=["admin"],
    include_in_schema=False  # This prevents the admin routes from showing in the auto-generated docs
)

# Movie routes
@router.post("/movies")
@limiter.limit(RATE_LIMIT_ADMIN)
async def create_movie(request: Request, movie_data: Dict[str, Any] = Body(...)):
    """
    Create a new movie
    """
    return await admin_controller.create_movie(movie_data)

@router.put("/movies/{movie_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def update_movie(
    request: Request,
    movie_id: str = Path(..., description="The ID of the movie to update"),
    movie_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing movie
    """
    return await admin_controller.update_movie(movie_id, movie_data)

@router.delete("/movies/{movie_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def delete_movie(
    request: Request,
    movie_id: str = Path(..., description="The ID of the movie to delete")
):
    """
    Delete a movie
    """
    return await admin_controller.delete_movie(movie_id)

# NEW: Get a single movie by ID for admin
@router.get("/movies/{movie_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_movie_by_id_admin(
    request: Request,
    movie_id: str = Path(..., description="The ID of the movie to get")
):
    """
    Get a movie by ID (Admin endpoint - returns full data)
    """
    # This calls the new controller function we added
    return await admin_controller.get_movie_by_id_admin(movie_id)


# Show routes
@router.post("/shows")
@limiter.limit(RATE_LIMIT_ADMIN)
async def create_show(request: Request, show_data: Dict[str, Any] = Body(...)):
    """
    Create a new show
    """
    return await admin_controller.create_show(show_data)

@router.put("/shows/{show_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def update_show(
    request: Request,
    show_id: str = Path(..., description="The ID of the show to update"),
    show_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing show
    """
    return await admin_controller.update_show(show_id, show_data)

@router.delete("/shows/{show_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def delete_show(
    request: Request,
    show_id: str = Path(..., description="The ID of the show to delete")
):
    """
    Delete a show and all its seasons and episodes
    """
    return await admin_controller.delete_show(show_id)

# NEW: Get a single show by ID for admin
@router.get("/shows/{show_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_show_by_id_admin(
    request: Request,
    show_id: str = Path(..., description="The ID of the show to get")
):
    """
    Get a show by ID (Admin endpoint - returns full data including seasons/episode IDs)
    """
    # This calls the new controller function we added
    return await admin_controller.get_show_by_id_admin(show_id)


@router.get("/seasons")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_all_seasons(
    request: Request,
    show_id: Optional[str] = Query(None, alias="showId"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("")
):
    """
    Get all seasons with optional filtering and pagination
    """
    return await admin_controller.get_all_seasons(show_id, page, limit, search)

@router.post("/shows/{show_id}/seasons")
@limiter.limit(RATE_LIMIT_ADMIN)
async def create_season(
    request: Request,
    show_id: str = Path(..., description="The ID of the show"),
    season_data: Dict[str, Any] = Body(...)
):
    """
    Create a new season for a show
    """
    return await admin_controller.create_season(show_id, season_data)

@router.put("/seasons/{season_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def update_season(
    request: Request,
    season_id: str = Path(..., description="The ID of the season to update"),
    season_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing season
    """
    return await admin_controller.update_season(season_id, season_data)

@router.delete("/seasons/{season_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def delete_season(
    request: Request,
    season_id: str = Path(..., description="The ID of the season to delete")
):
    """
    Delete a season and all its episodes
    """
    return await admin_controller.delete_season(season_id)

# NEW: Get a single season by ID for admin
@router.get("/seasons/{season_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_season_by_id_admin(
    request: Request,
    season_id: str = Path(..., description="The ID of the season to get")
):
    """
    Get a season by ID (Admin endpoint - returns full data including show info)
    """
    # This calls the new controller function we added
    return await admin_controller.get_season_by_id_admin(season_id)


# Episode routes
@router.get("/episodes")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_all_episodes(
    request: Request,
    season_id: Optional[str] = Query(None, alias="seasonId"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("")
):
    """
    Get all episodes with optional filtering and pagination
    """
    return await admin_controller.get_all_episodes(season_id, page, limit, search)

@router.post("/seasons/{season_id}/episodes")
@limiter.limit(RATE_LIMIT_ADMIN)
async def create_episode(
    request: Request,
    season_id: str = Path(..., description="The ID of the season"),
    episode_data: Dict[str, Any] = Body(...)
):
    """
    Create a new episode for a season
    """
    return await admin_controller.create_episode(season_id, episode_data)

# Batch Episode Creation Route
@router.post("/seasons/{season_id}/episodes/batch")
@limiter.limit(RATE_LIMIT_ADMIN) # Apply rate limiting
async def batch_create_episodes(
    request: Request,
    season_id: str = Path(..., description="The ID of the season to add episodes to"),
    episodes_data: List[Dict[str, Any]] = Body(..., description="List of episode data dictionaries")
):
    """
    Create multiple new episodes for a season in a single request.
    """
    return await admin_controller.batch_create_episodes(season_id, episodes_data)


@router.put("/episodes/{episode_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def update_episode(
    request: Request,
    episode_id: str = Path(..., description="The ID of the episode to update"),
    episode_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing episode
    """
    return await admin_controller.update_episode(episode_id, episode_data)

@router.delete("/episodes/{episode_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def delete_episode(
    request: Request,
    episode_id: str = Path(..., description="The ID of the episode to delete")
):
    """
    Delete an episode
    """
    return await admin_controller.delete_episode(episode_id)

# NEW: Get a single episode by ID for admin
@router.get("/episodes/{episode_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_episode_by_id_admin(
    request: Request,
    episode_id: str = Path(..., description="The ID of the episode to get")
):
    """
    Get an episode by ID (Admin endpoint - returns full data)
    """
    # This calls the new controller function we added
    return await admin_controller.get_episode_by_id_admin(episode_id)


# User management routes
@router.get("/users")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_all_users(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("")
):
    """
    Get all users with optional filtering and pagination
    """
    return await admin_controller.get_all_users(page, limit, search)

@router.get("/users/{user_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_user_by_id(
    request: Request,
    user_id: str = Path(..., description="The ID of the user to get")
):
    """
    Get a user by ID
    """
    # This calls the existing controller function, which is fine for admin
    return await admin_controller.get_user_by_id(user_id)

@router.put("/users/{user_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def update_user(
    request: Request,
    user_id: str = Path(..., description="The ID of the user to update"),
    user_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing user
    """
    # This calls the existing controller function
    return await admin_controller.update_user(user_id, user_data)

@router.delete("/users/{user_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def delete_user(
    request: Request,
    user_id: str = Path(..., description="The ID of the user to delete")
):
    """
    Delete a user
    """
    # This calls the existing controller function
    return await admin_controller.delete_user(user_id)

# Comment routes for admin
@router.get("/comments")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_all_comments(
    request: Request,
    content_type: Optional[str] = Query(None, description="Filter by content type (movie/show)"),
    content_id: Optional[str] = Query(None, description="Filter by content ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get all comments with optional filtering and pagination (Admin endpoint)
    """
    try:
        # Calculate skip value
        skip = (page - 1) * limit
        
        # Build query
        query = {}
        if content_type:
            query["content_type"] = content_type
        if content_id:
            from bson import ObjectId
            query["content_id"] = ObjectId(content_id)
        if user_id:
            query["user_id"] = ObjectId(user_id)
            
        # Get comments
        cursor = comment_collection.find(query).sort("createdAt", -1).skip(skip).limit(limit)
        comments = await cursor.to_list(length=limit)
        
        # Get total count
        total = await comment_collection.count_documents(query)
        
        return {
            "success": True,
            "data": {
                "comments": serialize_doc(comments),
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit
            }
        }
    except Exception as e:
        logger.error(f"Error in get_all_comments: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "message": str(e)}
        )

@router.get("/content/{content_type}/{content_id}/comments")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_content_comments(
    request: Request,
    content_type: str = Path(..., description="Type of content: movie or show"),
    content_id: str = Path(..., description="ID of the content to get comments for"),
    parent_id: Optional[str] = Query(None, description="ID of parent comment to get replies"),
    limit: int = Query(50, description="Number of comments to return"),
    skip: int = Query(0, description="Number of comments to skip")
):
    """
    Get comments for a specific content (Admin endpoint)
    """
    return await get_comments(content_id, content_type, parent_id, limit, skip)

@router.delete("/comments/{comment_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def admin_delete_comment(
    request: Request,
    comment_id: str = Path(..., description="ID of the comment to delete")
):
    """
    Delete a comment (Admin endpoint)
    """
    # Create a mock admin user object
    admin_user = {"role": "admin"}
    return await delete_comment(comment_id, admin_user)

# Report Admin Routes
@router.get("/reports")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_all_reports(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, resolved, rejected"),
    content_type: Optional[str] = Query(None, description="Filter by content type: movie, show")
):
    """
    Get all reports with pagination and optional filtering (Admin only)
    """
    return await report_controller.get_all_reports(page, limit, status, content_type)

@router.get("/reports/counts")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_report_counts(request: Request):
    """
    Get counts of reports by status and type (Admin only)
    """
    return await report_controller.get_report_counts()

@router.get("/reports/{report_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_report_by_id(
    request: Request,
    report_id: str = Path(..., description="The ID of the report to get")
):
    """
    Get a specific report by ID (Admin only)
    """
    return await report_controller.get_report_by_id(report_id)

@router.put("/reports/{report_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def update_report_status(
    request: Request,
    report_id: str = Path(..., description="The ID of the report to update"),
    update_data: ReportUpdate = Body(...)
):
    """
    Update a report's status (Admin only)
    """
    # Create a mock admin user object with _id field
    admin_user = {"role": "admin", "_id": "admin"}
    return await report_controller.update_report_status(report_id, update_data, admin_user)

@router.delete("/reports/{report_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def delete_report(
    request: Request,
    report_id: str = Path(..., description="The ID of the report to delete")
):
    """
    Delete a report (Admin only)
    """
    return await report_controller.delete_report(report_id)

@router.get("/reports/content/{content_type}/{content_id}")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_content_reports(
    request: Request,
    content_type: str = Path(..., description="Type of content: movie or show"),
    content_id: str = Path(..., description="ID of the content to get reports for"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get reports for a specific content item (Admin only)
    """
    return await report_controller.get_content_reports(content_id, content_type, page, limit)

# Admin Auth Routes
@router.get("/auth/verify")
@limiter.limit(RATE_LIMIT_ADMIN)
async def verify_admin_api_key(request: Request):
    """
    Verify admin API key and return basic admin info
    """
    # If we got here, it means the API key is valid (because of the middleware)
    return {
        "success": True,
        "data": {
            "role": "admin",
            "is_admin": True
        }
    }

@router.get("/auth/me")
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_admin_profile(request: Request):
    """
    Get admin user profile
    """
    # If we got here, it means the API key is valid (because of the middleware)
    return {
        "success": True,
        "data": {
            "_id": "admin",
            "username": "admin",
            "role": "admin",
            "is_admin": True,
            "email": "admin@odelu.com"
        }
    }
