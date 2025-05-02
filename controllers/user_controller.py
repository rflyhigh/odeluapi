from fastapi import HTTPException, status
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import user_watch_collection, movie_collection, episode_collection, season_collection, show_collection, serialize_doc

logger = logging.getLogger(__name__)

async def get_watch_history(user_id: str):
    try:
        # Get user's watch history
        cursor = user_watch_collection.find({"userId": user_id}).sort("watchedAt", DESCENDING).limit(20)
        
        # Build content details
        content_details = []
        async for item in cursor:
            item = serialize_doc(item)
            if item["contentType"] == "movie":
                # Get movie details
                movie = await movie_collection.find_one({"_id": ObjectId(item["contentId"])})
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
                # Get episode details
                episode = await episode_collection.find_one({"_id": ObjectId(item["contentId"])})
                if episode:
                    episode = serialize_doc(episode)
                    # Get season details
                    season = await season_collection.find_one({"_id": ObjectId(episode["seasonId"])})
                    season = serialize_doc(season) if season else None
                    # Get show details
                    show = None
                    if season:
                        show = await show_collection.find_one({"_id": ObjectId(season["showId"])})
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
        
        return {"success": True, "data": content_details}
    except Exception as e:
        logger.error(f"Error in get_watch_history: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_continue_watching(user_id: str):
    try:
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
                # Get movie details
                movie = await movie_collection.find_one({"_id": ObjectId(item["contentId"])})
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
                # Get episode details
                episode = await episode_collection.find_one({"_id": ObjectId(item["contentId"])})
                if episode:
                    episode = serialize_doc(episode)
                    # Get season details
                    season = await season_collection.find_one({"_id": ObjectId(episode["seasonId"])})
                    season = serialize_doc(season) if season else None
                    # Get show details
                    show = None
                    if season:
                        show = await show_collection.find_one({"_id": ObjectId(season["showId"])})
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
        
        return {"success": True, "data": content_details}
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