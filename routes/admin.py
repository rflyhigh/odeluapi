from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException
from typing import Optional, Dict, Any
import logging

from controllers import admin_controller
from middleware.api_auth import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

# Apply API key authentication to all admin routes
router = APIRouter(dependencies=[Depends(verify_api_key)])

# Movie routes
@router.post("/movies")
async def create_movie(movie_data: Dict[str, Any] = Body(...)):
    """
    Create a new movie
    """
    return await admin_controller.create_movie(movie_data)

@router.put("/movies/{movie_id}")
async def update_movie(
    movie_id: str = Path(..., description="The ID of the movie to update"),
    movie_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing movie
    """
    return await admin_controller.update_movie(movie_id, movie_data)

@router.delete("/movies/{movie_id}")
async def delete_movie(movie_id: str = Path(..., description="The ID of the movie to delete")):
    """
    Delete a movie
    """
    return await admin_controller.delete_movie(movie_id)

# Show routes
@router.post("/shows")
async def create_show(show_data: Dict[str, Any] = Body(...)):
    """
    Create a new show
    """
    return await admin_controller.create_show(show_data)

@router.put("/shows/{show_id}")
async def update_show(
    show_id: str = Path(..., description="The ID of the show to update"),
    show_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing show
    """
    return await admin_controller.update_show(show_id, show_data)

@router.delete("/shows/{show_id}")
async def delete_show(show_id: str = Path(..., description="The ID of the show to delete")):
    """
    Delete a show and all its seasons and episodes
    """
    return await admin_controller.delete_show(show_id)

@router.get("/seasons")
async def get_all_seasons(
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
async def create_season(
    show_id: str = Path(..., description="The ID of the show"),
    season_data: Dict[str, Any] = Body(...)
):
    """
    Create a new season for a show
    """
    return await admin_controller.create_season(show_id, season_data)

@router.put("/seasons/{season_id}")
async def update_season(
    season_id: str = Path(..., description="The ID of the season to update"),
    season_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing season
    """
    return await admin_controller.update_season(season_id, season_data)

@router.delete("/seasons/{season_id}")
async def delete_season(season_id: str = Path(..., description="The ID of the season to delete")):
    """
    Delete a season and all its episodes
    """
    return await admin_controller.delete_season(season_id)

# Episode routes
@router.get("/episodes")
async def get_all_episodes(
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
async def create_episode(
    season_id: str = Path(..., description="The ID of the season"),
    episode_data: Dict[str, Any] = Body(...)
):
    """
    Create a new episode for a season
    """
    return await admin_controller.create_episode(season_id, episode_data)

@router.put("/episodes/{episode_id}")
async def update_episode(
    episode_id: str = Path(..., description="The ID of the episode to update"),
    episode_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing episode
    """
    return await admin_controller.update_episode(episode_id, episode_data)

@router.delete("/episodes/{episode_id}")
async def delete_episode(episode_id: str = Path(..., description="The ID of the episode to delete")):
    """
    Delete an episode
    """
    return await admin_controller.delete_episode(episode_id)

# User management routes
@router.get("/users")
async def get_all_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("")
):
    """
    Get all users with optional filtering and pagination
    """
    return await admin_controller.get_all_users(page, limit, search)

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: str = Path(..., description="The ID of the user to get")
):
    """
    Get a user by ID
    """
    return await admin_controller.get_user_by_id(user_id)

@router.put("/users/{user_id}")
async def update_user(
    user_id: str = Path(..., description="The ID of the user to update"),
    user_data: Dict[str, Any] = Body(...)
):
    """
    Update an existing user
    """
    return await admin_controller.update_user(user_id, user_data)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str = Path(..., description="The ID of the user to delete")
):
    """
    Delete a user
    """
    return await admin_controller.delete_user(user_id)