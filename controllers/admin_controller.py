# admin_controller.py
from fastapi import HTTPException, status, Depends
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
import logging
from datetime import datetime

# Ensure these imports are correct based on your project structure
from database import movie_collection, show_collection, season_collection, episode_collection, user_collection, watchlist_collection, user_watch_collection, serialize_doc
from utils.auth import get_password_hash
# Import secure_video_url but we won't use it in the admin fetch functions
from utils.video_security import secure_video_url # Keep this import if other functions use it

logger = logging.getLogger(__name__)

# MOVIE CONTROLLERS
async def create_movie(movie_data: Dict[str, Any]):
    try:
        # Add timestamps
        movie_data["createdAt"] = datetime.now()
        movie_data["updatedAt"] = datetime.now()

        # Insert into database
        result = await movie_collection.insert_one(movie_data)

        # Get the created movie
        new_movie = await movie_collection.find_one({"_id": result.inserted_id})

        return {"success": True, "data": serialize_doc(new_movie)}
    except Exception as e:
        logger.error(f"Error in create_movie: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def update_movie(movie_id: str, movie_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid movie ID format"})

        # Update timestamp
        movie_data["updatedAt"] = datetime.now()

        # Update movie
        result = await movie_collection.update_one(
            {"_id": ObjectId(movie_id)},
            {"$set": movie_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Movie not found"})

        # Get the updated movie
        updated_movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})

        return {"success": True, "data": serialize_doc(updated_movie)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_movie: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def delete_movie(movie_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid movie ID format"})

        # Delete movie
        result = await movie_collection.delete_one({"_id": ObjectId(movie_id)})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Movie not found"})

        # Delete related watch history
        await user_watch_collection.delete_many({"contentType": "movie", "contentId": ObjectId(movie_id)})

        # Delete from watchlists
        await watchlist_collection.delete_many({"contentType": "movie", "contentId": ObjectId(movie_id)})

        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_movie: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

# NEW: Get a single movie by ID for admin
async def get_movie_by_id_admin(movie_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid movie ID format"})

        # Find movie by ID
        movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})

        if not movie:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Movie not found"})

        # Serialize and return the full document (including original links)
        return {"success": True, "data": serialize_doc(movie)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_movie_by_id_admin: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})


# SHOW CONTROLLERS
async def create_show(show_data: Dict[str, Any]):
    try:
        # Add timestamps
        show_data["createdAt"] = datetime.now()
        show_data["updatedAt"] = datetime.now()

        # Insert into database
        result = await show_collection.insert_one(show_data)

        # Get the created show
        new_show = await show_collection.find_one({"_id": result.inserted_id})

        return {"success": True, "data": serialize_doc(new_show)}
    except Exception as e:
        logger.error(f"Error in create_show: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def update_show(show_id: str, show_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})

        # Update timestamp
        show_data["updatedAt"] = datetime.now()

        # Update show
        result = await show_collection.update_one(
            {"_id": ObjectId(show_id)},
            {"$set": show_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})

        # Get the updated show
        updated_show = await show_collection.find_one({"_id": ObjectId(show_id)})

        return {"success": True, "data": serialize_doc(updated_show)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_show: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def delete_show(show_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})

        # Find the show
        show = await show_collection.find_one({"_id": ObjectId(show_id)})

        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})

        # Find all seasons for this show
        seasons = []
        async for season in season_collection.find({"showId": ObjectId(show_id)}):
            seasons.append(season)

        # Get all season IDs
        season_ids = [season["_id"] for season in seasons]

        # Find all episodes for these seasons
        episode_ids = []
        if season_ids:
            async for episode in episode_collection.find({"seasonId": {"$in": season_ids}}):
                episode_ids.append(episode["_id"])

        # Delete all episodes
        if episode_ids:
            await episode_collection.delete_many({"_id": {"$in": episode_ids}})

            # Delete episode watch history
            await user_watch_collection.delete_many({"contentType": "episode", "contentId": {"$in": episode_ids}})

        # Delete all seasons
        await season_collection.delete_many({"showId": ObjectId(show_id)})

        # Delete the show
        await show_collection.delete_one({"_id": ObjectId(show_id)})

        # Delete from watchlists
        await watchlist_collection.delete_many({"contentType": "show", "contentId": ObjectId(show_id)})

        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_show: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

# NEW: Get a single show by ID for admin
async def get_show_by_id_admin(show_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})

        # Find show by ID
        show = await show_collection.find_one({"_id": ObjectId(show_id)})

        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})

        # Get seasons for this show (full season data, not just IDs)
        seasons_cursor = season_collection.find({"showId": ObjectId(show_id)}).sort("seasonNumber", 1)
        seasons = []
        async for season in seasons_cursor:
            season_dict = serialize_doc(season)
            # Optionally fetch episode IDs for each season if needed in admin view
            # For now, we'll just return the season details
            seasons.append(season_dict)

        # Add seasons to show
        show_dict = serialize_doc(show)
        show_dict["seasons"] = seasons # Include full season details

        # Note: We are NOT fetching all episodes here to avoid massive payloads.
        # The admin frontend will fetch episodes for a specific season separately.

        return {"success": True, "data": show_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_show_by_id_admin: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})


# SEASON CONTROLLERS
async def create_season(show_id: str, season_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})

        # Check if show exists
        show = await show_collection.find_one({"_id": ObjectId(show_id)})
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})

        # Add showId and timestamps
        season_data["showId"] = ObjectId(show_id)
        season_data["createdAt"] = datetime.now()
        season_data["updatedAt"] = datetime.now()

        # Insert into database
        result = await season_collection.insert_one(season_data)

        # Add season to show
        await show_collection.update_one(
            {"_id": ObjectId(show_id)},
            {"$push": {"seasons": result.inserted_id}}
        )

        # Get the created season
        new_season = await season_collection.find_one({"_id": result.inserted_id})

        return {"success": True, "data": serialize_doc(new_season)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_season: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def update_season(season_id: str, season_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid season ID format"})

        # Update timestamp
        season_data["updatedAt"] = datetime.now()

        # Update season
        result = await season_collection.update_one(
            {"_id": ObjectId(season_id)},
            {"$set": season_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})

        # Get the updated season
        updated_season = await season_collection.find_one({"_id": ObjectId(season_id)})

        return {"success": True, "data": serialize_doc(updated_season)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_season: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def delete_season(season_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid season ID format"})

        # Find the season
        season = await season_collection.find_one({"_id": ObjectId(season_id)})

        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})

        # Find all episodes for this season
        episode_ids = []
        async for episode in episode_collection.find({"seasonId": ObjectId(season_id)}):
            episode_ids.append(episode["_id"])

        # Delete all episodes
        await episode_collection.delete_many({"seasonId": ObjectId(season_id)})

        # Delete episode watch history
        if episode_ids:
            await user_watch_collection.delete_many({"contentType": "episode", "contentId": {"$in": episode_ids}})

        # Remove season from show
        await show_collection.update_one(
            {"_id": season["showId"]},
            {"$pull": {"seasons": ObjectId(season_id)}}
        )

        # Delete the season
        await season_collection.delete_one({"_id": ObjectId(season_id)})

        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_season: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def get_all_seasons(show_id: Optional[str] = None, page: int = 1, limit: int = 20, search: str = ""):
    try:
        skip = (page - 1) * limit

        # Build query
        query = {}
        if show_id:
            # Validate ObjectId
            if not ObjectId.is_valid(show_id):
                raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})
            query["showId"] = ObjectId(show_id)

        if search:
            query["title"] = {"$regex": search, "$options": "i"}

        # Execute query with pagination
        cursor = season_collection.find(query).sort([("showId", ASCENDING), ("seasonNumber", ASCENDING)]).skip(skip).limit(limit)

        # Convert to list and add show details
        seasons = []
        async for season in cursor:
            season_dict = serialize_doc(season)
            # Get show details
            show = await show_collection.find_one({"_id": ObjectId(season["showId"])})
            if show:
                season_dict["showId"] = {
                    "_id": str(show["_id"]),
                    "title": show["title"]
                }
            seasons.append(season_dict)

        # Get total count for pagination
        total = await season_collection.count_documents(query)

        return {
            "success": True,
            "data": seasons,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_seasons: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

# NEW: Get a single season by ID for admin
async def get_season_by_id_admin(season_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid season ID format"})

        # Find season by ID
        season = await season_collection.find_one({"_id": ObjectId(season_id)})

        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})

        # Get show details for context
        show = await show_collection.find_one({"_id": season["showId"]})
        if show:
            season_dict = serialize_doc(season)
            season_dict["showId"] = {
                "_id": str(show["_id"]),
                "title": show["title"]
            }
            return {"success": True, "data": season_dict}
        else:
             # Handle case where show is missing (shouldn't happen if data is consistent)
             season_dict = serialize_doc(season)
             season_dict["showId"] = None # Or handle as an error
             return {"success": True, "data": season_dict}


    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_season_by_id_admin: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})


# EPISODE CONTROLLERS
async def create_episode(season_id: str, episode_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid season ID format"})

        # Check if season exists
        season = await season_collection.find_one({"_id": ObjectId(season_id)})
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})

        # Add seasonId and timestamps
        episode_data["seasonId"] = ObjectId(season_id)
        episode_data["createdAt"] = datetime.now()
        episode_data["updatedAt"] = datetime.now()

        # Insert into database
        result = await episode_collection.insert_one(episode_data)

        # Add episode to season
        await season_collection.update_one(
            {"_id": ObjectId(season_id)},
            {"$push": {"episodes": result.inserted_id}}
        )

        # Get the created episode
        new_episode = await episode_collection.find_one({"_id": result.inserted_id})

        return {"success": True, "data": serialize_doc(new_episode)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_episode: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def update_episode(episode_id: str, episode_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})

        # Update timestamp
        episode_data["updatedAt"] = datetime.now()

        # Update episode
        result = await episode_collection.update_one(
            {"_id": ObjectId(episode_id)},
            {"$set": episode_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})

        # Get the updated episode
        updated_episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})

        return {"success": True, "data": serialize_doc(updated_episode)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_episode: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def delete_episode(episode_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})

        # Find the episode
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})

        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})

        # Remove episode from season
        await season_collection.update_one(
            {"_id": episode["seasonId"]},
            {"$pull": {"episodes": ObjectId(episode_id)}}
        )

        # Delete the episode
        await episode_collection.delete_one({"_id": ObjectId(episode_id)})

        # Delete watch history
        await user_watch_collection.delete_many({"contentType": "episode", "contentId": ObjectId(episode_id)})

        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_episode: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

# Batch Episode Creation
async def batch_create_episodes(season_id: str, episodes_data: List[Dict[str, Any]]):
    try:
        # Validate Season ObjectId
        if not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid season ID format"})

        # Check if season exists
        season = await season_collection.find_one({"_id": ObjectId(season_id)})
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})

        if not episodes_data:
            return {"success": True, "data": [], "message": "No episodes provided for batch creation."}

        episodes_to_insert = []
        episode_ids_to_push = []
        now = datetime.now()

        for episode_data in episodes_data:
            # Basic validation for each episode in the batch
            if not isinstance(episode_data, dict):
                 raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode data format in batch."})
            if not episode_data.get("episodeNumber") or not isinstance(episode_data["episodeNumber"], int) or episode_data["episodeNumber"] <= 0:
                 raise HTTPException(status_code=400, detail={"success": False, "message": f"Invalid or missing episodeNumber in batch data for episode {episode_data.get('episodeNumber')}."})
            if not episode_data.get("title") or not isinstance(episode_data["title"], str):
                 raise HTTPException(status_code=400, detail={"success": False, "message": f"Invalid or missing title in batch data for episode {episode_data.get('episodeNumber')}."})
            if not episode_data.get("links") or not isinstance(episode_data["links"], list) or len(episode_data["links"]) == 0:
                 raise HTTPException(status_code=400, detail={"success": False, "message": f"Invalid or missing links in batch data for episode {episode_data.get('episodeNumber')}."})

            # Add seasonId and timestamps
            episode_data["seasonId"] = ObjectId(season_id)
            episode_data["createdAt"] = now
            episode_data["updatedAt"] = now

            # Ensure links have name and url
            valid_links = []
            for link in episode_data["links"]:
                if isinstance(link, dict) and link.get("name") and link.get("url"):
                    valid_links.append(link)
                else:
                     logger.warning(f"Skipping invalid link format for episode {episode_data.get('episodeNumber')}: {link}")

            if not valid_links:
                 raise HTTPException(status_code=400, detail={"success": False, "message": f"No valid links found for episode {episode_data.get('episodeNumber')} in batch data."})

            episode_data["links"] = valid_links

            episodes_to_insert.append(episode_data)

        # Insert episodes in bulk
        insert_results = await episode_collection.insert_many(episodes_to_insert)
        episode_ids_to_push = insert_results.inserted_ids

        # Add episode IDs to the season document
        if episode_ids_to_push:
            await season_collection.update_one(
                {"_id": ObjectId(season_id)},
                {"$push": {"episodes": {"$each": episode_ids_to_push}}}
            )

        # Fetch the newly created episodes to return
        new_episodes = []
        if episode_ids_to_push:
             async for episode in episode_collection.find({"_id": {"$in": episode_ids_to_push}}):
                 new_episodes.append(serialize_doc(episode))


        return {"success": True, "data": new_episodes, "message": f"Successfully created {len(new_episodes)} episodes."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch_create_episodes: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})


async def get_all_episodes(season_id: Optional[str] = None, page: int = 1, limit: int = 20, search: str = ""):
    try:
        skip = (page - 1) * limit

        # Build query
        query = {}
        if season_id:
            # Validate ObjectId
            if not ObjectId.is_valid(season_id):
                raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid season ID format"})
            query["seasonId"] = ObjectId(season_id)

        if search:
            query["title"] = {"$regex": search, "$options": "i"}

        # Execute query with pagination
        cursor = episode_collection.find(query).sort([("seasonId", ASCENDING), ("episodeNumber", ASCENDING)]).skip(skip).limit(limit)

        # Convert to list and add show/season details
        episodes = []
        async for episode in cursor:
            episode_dict = serialize_doc(episode)
            # Get season details
            season = await season_collection.find_one({"_id": ObjectId(episode["seasonId"])})
            if season:
                # Get show details
                show = await show_collection.find_one({"_id": ObjectId(season["showId"])})
                episode_dict["seasonId"] = {
                    "_id": str(season["_id"]),
                    "seasonNumber": season["seasonNumber"],
                    "showId": {
                        "_id": str(show["_id"]) if show else None,
                        "title": show["title"] if show else "Unknown Show"
                    }
                }
            episodes.append(episode_dict)

        # Get total count for pagination
        total = await episode_collection.count_documents(query)

        return {
            "success": True,
            "data": episodes,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_episodes: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

# NEW: Get a single episode by ID for admin
async def get_episode_by_id_admin(episode_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})

        # Find episode by ID
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})

        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})

        # Get season and show info for context
        season = await season_collection.find_one({"_id": episode["seasonId"]})
        show = None
        if season:
            show = await show_collection.find_one({"_id": season["showId"]})

        episode_dict = serialize_doc(episode)

        # Include season and show details for context in the admin view
        episode_dict["seasonId"] = {
            "_id": str(season["_id"]) if season else None,
            "seasonNumber": season["seasonNumber"] if season else None,
            "showId": {
                "_id": str(show["_id"]) if show else None,
                "title": show["title"] if show else "Unknown Show"
            } if show else None
        }

        # Return the full episode document including original links
        return {"success": True, "data": episode_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_episode_by_id_admin: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

# USER MANAGEMENT
async def get_all_users(page: int = 1, limit: int = 20, search: str = ""):
    try:
        skip = (page - 1) * limit

        # Build query
        query = {}
        if search:
            query["$or"] = [
                {"username": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"name": {"$regex": search, "$options": "i"}}
            ]

        # Execute query with pagination
        cursor = user_collection.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)

        # Convert to list and remove sensitive data
        users = []
        async for user in cursor:
            user_dict = serialize_doc(user)
            if "hashed_password" in user_dict:
                del user_dict["hashed_password"]
            users.append(user_dict)

        # Get total count for pagination
        total = await user_collection.count_documents(query)

        return {
            "success": True,
            "data": users,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except Exception as e:
        logger.error(f"Error in get_all_users: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_user_by_id(user_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid user ID format"})

        # Find user by ID
        user = await user_collection.find_one({"_id": ObjectId(user_id)})

        if not user:
            raise HTTPException(status_code=404, detail={"success": False, "message": "User not found"})

        # Remove sensitive data
        user_dict = serialize_doc(user)
        if "hashed_password" in user_dict:
            del user_dict["hashed_password"]

        return {"success": True, "data": user_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def update_user(user_id: str, user_data: Dict[str, Any]):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid user ID format"})

        # Update timestamp
        user_data["updatedAt"] = datetime.now()

        # Handle password update if provided
        if "password" in user_data:
            user_data["hashed_password"] = get_password_hash(user_data["password"])
            del user_data["password"]

        # Update user
        result = await user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": user_data}
        )


        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "User not found"})

        # Get the updated user
        updated_user = await user_collection.find_one({"_id": ObjectId(user_id)})

        # Remove sensitive data
        user_dict = serialize_doc(updated_user)
        if "hashed_password" in user_dict:
            del user_dict["hashed_password"]

        return {"success": True, "data": user_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_user: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

async def delete_user(user_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid user ID format"})

        # Delete user
        result = await user_collection.delete_one({"_id": ObjectId(user_id)})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail={"success": False, "message": "User not found"})

        # Delete user's watchlist items
        await watchlist_collection.delete_many({"userId": user_id})

        # Delete user's watch history
        await user_watch_collection.delete_many({"userId": user_id})

        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_user: {str(e)}")
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})

