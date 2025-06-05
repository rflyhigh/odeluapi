from fastapi import HTTPException, status
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import user_watch_collection, movie_collection, episode_collection, season_collection, show_collection, serialize_doc, get_cache, set_cache, delete_cache, user_collection, watchlist_collection

logger = logging.getLogger(__name__)

async def get_watch_history(user_id: str):
    try:
        # Try to get from cache first
        cache_key = f"user:{user_id}:watch_history"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Get user's watch history
        cursor = user_watch_collection.find({"userId": user_id}).sort("watchedAt", DESCENDING).limit(20)
        
        # Build content details
        content_details = []
        async for item in cursor:
            item = serialize_doc(item)
            if item["contentType"] == "movie":
                # Get movie details with projection
                projection = {"title": 1, "image": 1, "duration": 1}
                movie = await movie_collection.find_one({"_id": ObjectId(item["contentId"])}, projection)
                if movie:
                    movie = serialize_doc(movie)
                    content_details.append({
                        "id": item["contentId"],
                        "type": "movie",
                        "title": movie.get("title", "Unknown Movie"),
                        "image": movie.get("image", ""),
                        "duration": movie.get("duration", ""),
                        "progress": item.get("progress", 0),
                        "completed": item.get("completed", False),
                        "watchedAt": item.get("watchedAt")
                    })
            else:  # episode
                # Get episode details with projection
                episode_projection = {"title": 1, "image": 1, "episodeNumber": 1, "seasonId": 1}
                episode = await episode_collection.find_one({"_id": ObjectId(item["contentId"])}, episode_projection)
                if episode:
                    episode = serialize_doc(episode)
                    # Get season details with projection
                    season_projection = {"seasonNumber": 1, "showId": 1}
                    season = await season_collection.find_one({"_id": ObjectId(episode["seasonId"])}, season_projection)
                    season = serialize_doc(season) if season else None
                    # Get show details with projection
                    show = None
                    if season:
                        show_projection = {"title": 1, "image": 1}
                        show = await show_collection.find_one({"_id": ObjectId(season["showId"])}, show_projection)
                        show = serialize_doc(show) if show else None
                    
                    content_details.append({
                        "id": item["contentId"],
                        "type": "episode",
                        "showId": season["showId"] if season else None,
                        "showTitle": show.get("title", "Unknown Show") if show else "Unknown Show",
                        "showImage": show.get("image", "") if show else "",
                        "seasonNumber": season.get("seasonNumber", 0) if season else 0,
                        "episodeNumber": episode.get("episodeNumber", 0),
                        "title": episode.get("title", "Unknown Episode"),
                        "image": episode.get("image", ""),
                        "progress": item.get("progress", 0),
                        "completed": item.get("completed", False),
                        "watchedAt": item.get("watchedAt")
                    })
        
        result = {
            "success": True, 
            "data": {
                "items": content_details,
                "timezone_note": "All timestamps are in UTC and will be converted to user's timezone by middleware"
            }
        }
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_watch_history: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})


async def get_recently_added(limit: int = 5):
    try:
        # Try to get from cache first
        cache_key = f"recently_added:{limit}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Get recently added movies
        recent_movies_cursor = movie_collection.find(
            {}, 
            {"title": 1, "image": 1, "createdAt": 1}
        ).sort("createdAt", -1).limit(limit)
        
        recent_movies = []
        async for movie in recent_movies_cursor:
            movie_dict = serialize_doc(movie)
            movie_dict["type"] = "movie"
            recent_movies.append(movie_dict)
            
        # Get recently added episodes
        recent_episodes_cursor = episode_collection.find(
            {}, 
            {"title": 1, "image": 1, "createdAt": 1, "seasonId": 1, "episodeNumber": 1}
        ).sort("createdAt", -1).limit(limit)
        
        recent_episodes = []
        async for episode in recent_episodes_cursor:
            episode_dict = serialize_doc(episode)
            
            # Get season details
            season = await season_collection.find_one(
                {"_id": ObjectId(episode["seasonId"])},
                {"seasonNumber": 1, "showId": 1}
            )
            
            if season:
                # Get show details
                show = await show_collection.find_one(
                    {"_id": ObjectId(season["showId"])},
                    {"title": 1, "image": 1}
                )
                
                if show:
                    episode_dict["type"] = "episode"
                    episode_dict["showId"] = str(season["showId"])
                    episode_dict["showTitle"] = show["title"]
                    episode_dict["showImage"] = show["image"]
                    episode_dict["seasonNumber"] = season["seasonNumber"]
                    recent_episodes.append(episode_dict)
        
        # Combine and sort by createdAt
        recent_items = recent_movies + recent_episodes
        recent_items.sort(key=lambda x: x["createdAt"], reverse=True)
        
        # Take only the most recent items
        recent_items = recent_items[:limit]
        
        result = {
            "success": True, 
            "data": {
                "items": recent_items,
                "timezone_note": "All timestamps are in UTC and will be converted to user's timezone by middleware"
            }
        }
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_recently_added: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_continue_watching(user_id: str):
    try:
        # Try to get from cache first
        cache_key = f"user:{user_id}:continue_watching"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Get incomplete watches (any progress or recently watched but not completed)
        cursor = user_watch_collection.find({
            "userId": user_id,
            "$or": [
                {"progress": {"$gt": 0, "$lt": 90}},
                {"completed": False}
            ]
        }).sort("watchedAt", DESCENDING).limit(10)
        
        # Build content details
        content_details = []
        async for item in cursor:
            item = serialize_doc(item)
            if item["contentType"] == "movie":
                # Get movie details with projection
                projection = {"title": 1, "image": 1, "duration": 1}
                movie = await movie_collection.find_one({"_id": ObjectId(item["contentId"])}, projection)
                if movie:
                    movie = serialize_doc(movie)
                    content_details.append({
                        "id": item["contentId"],
                        "type": "movie",
                        "title": movie.get("title", "Unknown Movie"),
                        "image": movie.get("image", ""),
                        "duration": movie.get("duration", ""),
                        "progress": item.get("progress", 0),
                        "completed": item.get("completed", False),
                        "watchedAt": item.get("watchedAt")
                    })
            else:  # episode
                # Get episode details with projection
                episode_projection = {"title": 1, "image": 1, "episodeNumber": 1, "seasonId": 1}
                episode = await episode_collection.find_one({"_id": ObjectId(item["contentId"])}, episode_projection)
                if episode:
                    episode = serialize_doc(episode)
                    # Get season details with projection
                    season_projection = {"seasonNumber": 1, "showId": 1}
                    season = await season_collection.find_one({"_id": ObjectId(episode["seasonId"])}, season_projection)
                    season = serialize_doc(season) if season else None
                    # Get show details with projection
                    show = None
                    if season:
                        show_projection = {"title": 1, "image": 1}
                        show = await show_collection.find_one({"_id": ObjectId(season["showId"])}, show_projection)
                        show = serialize_doc(show) if show else None
                    
                    content_details.append({
                        "id": item["contentId"],
                        "type": "episode",
                        "showId": season["showId"] if season else None,
                        "showTitle": show.get("title", "Unknown Show") if show else "Unknown Show",
                        "showImage": show.get("image", "") if show else "",
                        "seasonNumber": season.get("seasonNumber", 0) if season else 0,
                        "episodeNumber": episode.get("episodeNumber", 0),
                        "title": episode.get("title", "Unknown Episode"),
                        "image": episode.get("image", ""),
                        "progress": item.get("progress", 0),
                        "completed": item.get("completed", False),
                        "watchedAt": item.get("watchedAt")
                    })
        
        result = {
            "success": True, 
            "data": {
                "items": content_details,
                "timezone_note": "All timestamps are in UTC and will be converted to user's timezone by middleware"
            }
        }
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_continue_watching: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_user_by_token(user_data):
    """
    Get user profile from token data
    """
    try:
        user_id = user_data.get("_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail={"success": False, "message": "Invalid authentication token"}
            )
            
        # Return user data (excluding sensitive info)
        user_data_copy = dict(user_data)
        if "hashed_password" in user_data_copy:
            del user_data_copy["hashed_password"]
            
        return {"success": True, "data": user_data_copy}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_by_token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def delete_watch_history(user_id: str):
    """
    Delete all watch history for a user
    """
    try:
        # Delete all watch history records
        result = await user_watch_collection.delete_many({"userId": user_id})
        
        # Clear user cache
        await delete_cache(f"user:{user_id}:watch_history")
        await delete_cache(f"user:{user_id}:continue_watching")
        
        return {
            "success": True, 
            "data": {"deleted_count": result.deleted_count}
        }
    except Exception as e:
        logger.error(f"Error in delete_watch_history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def delete_account(user_id: str):
    """
    Delete a user account and all associated data
    """
    try:
        # Delete all user data
        await user_watch_collection.delete_many({"userId": user_id})
        await watchlist_collection.delete_many({"userId": user_id})
        
        # Delete the user
        result = await user_collection.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "User not found"}
            )
        
        # Clear all user cache
        await delete_cache_pattern(f"user:{user_id}:*")
        
        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )
