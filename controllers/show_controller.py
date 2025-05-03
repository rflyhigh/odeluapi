from fastapi import HTTPException
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import show_collection, season_collection, episode_collection, user_watch_collection, serialize_doc, get_cache, set_cache, delete_cache, delete_cache_pattern
from utils.video_security import secure_video_url

logger = logging.getLogger(__name__)

async def get_all_shows(tag: Optional[str] = None, search: Optional[str] = None, 
                        limit: int = 20, page: int = 1):
    try:
        # Try to get from cache first
        cache_key = f"shows:list:{tag or 'all'}:{search or 'none'}:{page}:{limit}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        skip = (page - 1) * limit
        
        # Build query
        query = {}
        if tag:
            query["tags"] = tag
        
        if search:
            query["title"] = {"$regex": search, "$options": "i"}
        
        # Define projection to limit fields returned
        projection = {
            "title": 1, 
            "image": 1, 
            "startYear": 1, 
            "endYear": 1,
            "tags": 1, 
            "featured": 1,
            "rating": 1,
            "createdAt": 1
        }
        
        # Execute query with pagination
        cursor = show_collection.find(query, projection).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        
        # Convert to list and add type field
        shows = []
        async for show in cursor:
            show_dict = serialize_doc(show)
            show_dict["type"] = "show"  # Add type field
            shows.append(show_dict)
        
        # Get total count for pagination
        total = await show_collection.count_documents(query)
        
        result = {
            "success": True,
            "data": shows,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_all_shows: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_featured_shows():
    try:
        # Try to get from cache first
        cache_key = "shows:featured"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Find featured shows with projection
        projection = {
            "title": 1, 
            "image": 1, 
            "startYear": 1, 
            "endYear": 1,
            "tags": 1, 
            "rating": 1,
            "description": 1,
            "coverImage": 1
        }
        
        cursor = show_collection.find({"featured": True}, projection).limit(10)
        
        # Convert to list and add type field
        featured_shows = []
        async for show in cursor:
            show_dict = serialize_doc(show)
            show_dict["type"] = "show"  # Add type field
            featured_shows.append(show_dict)
        
        result = {"success": True, "data": featured_shows}
        
        # Cache the result
        await set_cache(cache_key, result, 600)  # Cache for 10 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_featured_shows: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
    
async def get_show_by_id(show_id: str, user_id: Optional[str] = None):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})
        
        # Try to get from cache first (without watch history)
        cache_key = f"shows:detail:{show_id}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        # Find show by ID
        show = await show_collection.find_one({"_id": ObjectId(show_id)})
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
        
        # Get seasons for this show
        seasons_cursor = season_collection.find({"showId": ObjectId(show_id)}).sort("seasonNumber", 1)
        seasons = []
        async for season in seasons_cursor:
            season_dict = serialize_doc(season)
            
            # Get episodes for this season with projection
            episode_projection = {
                "title": 1,
                "episodeNumber": 1,
                "image": 1,
                "description": 1,
                "duration": 1,
                "seasonId": 1
            }
            
            episodes_cursor = episode_collection.find(
                {"seasonId": season["_id"]}, 
                episode_projection
            ).sort("episodeNumber", 1)
            
            episodes = []
            async for episode in episodes_cursor:
                episode_dict = serialize_doc(episode)
                episodes.append(episode_dict)
            
            season_dict["episodes"] = episodes
            seasons.append(season_dict)
        
        # Add seasons to show
        show_dict = serialize_doc(show)
        show_dict["seasons"] = seasons
        show_dict["type"] = "show"  # Add type field
        
        # Get related shows based on tags with projection
        projection = {
            "title": 1, 
            "image": 1, 
            "startYear": 1, 
            "tags": 1, 
            "rating": 1
        }
        
        related_cursor = show_collection.find({
            "_id": {"$ne": ObjectId(show_id)},
            "tags": {"$in": show.get("tags", [])}
        }, projection).limit(6)
        
        # Convert to list and add type field
        related_shows = []
        async for related in related_cursor:
            related_dict = serialize_doc(related)
            related_dict["type"] = "show"  # Add type field
            related_shows.append(related_dict)
        
        result = {
            "success": True,
            "data": show_dict,
            "related": related_shows,
            "watchHistory": []
        }
        
        # Get user watch history if user_id provided
        if user_id:
            # Get all episode IDs from the show
            episode_ids = []
            for season in seasons:
                for episode in season.get("episodes", []):
                    episode_ids.append(ObjectId(episode["_id"]))
            
            if episode_ids:
                # Get watch status for all episodes
                watch_cursor = user_watch_collection.find({
                    "userId": user_id,
                    "contentType": "episode",
                    "contentId": {"$in": episode_ids}
                })
                
                watch_history = []
                async for watch in watch_cursor:
                    watch_history.append({
                        "episodeId": str(watch["contentId"]),
                        "progress": watch.get("progress", 0),
                        "completed": watch.get("completed", False),
                        "lastWatched": watch.get("watchedAt")
                    })
                
                result["watchHistory"] = watch_history
        else:
            # Cache the result (only if no user-specific data)
            await set_cache(cache_key, result, 1800)  # Cache for 30 minutes
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_show_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_episode_by_id(episode_id: str, user_id: Optional[str] = None):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})
        
        # Try to get from cache first (without watch status)
        cache_key = f"episodes:detail:{episode_id}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        # Find episode by ID
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})
        
        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})
        
        # Get season info
        season = await season_collection.find_one({"_id": episode["seasonId"]})
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
        
        # Get show info with projection
        show_projection = {"title": 1, "image": 1}
        show = await show_collection.find_one({"_id": season["showId"]}, show_projection)
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
        
        # Build response object
        episode_dict = serialize_doc(episode)
        
        # Debug log to check links before securing
        if "links" in episode_dict and episode_dict["links"]:
            logger.info(f"Episode {episode_id} has {len(episode_dict['links'])} links before securing")
            for i, link in enumerate(episode_dict["links"]):
                logger.info(f"Link {i}: {link.get('name')} - URL exists: {'url' in link}")
                if 'url' in link:
                    # Secure video URLs in links
                    original_url = link["url"]
                    link["url"] = secure_video_url(original_url)
                    logger.info(f"Secured URL: original length {len(original_url)} -> new length {len(link['url'])}")
                else:
                    logger.warning(f"Link {i} has no URL key")
        else:
            logger.warning(f"Episode {episode_id} has no links or empty links array")
            # If no links found, add a default message
            episode_dict["links"] = episode_dict.get("links", [])
            if not episode_dict["links"]:
                logger.warning("No links found for episode, check your database")
        
        episode_dict["seasonId"] = {
            "_id": str(season["_id"]),
            "showId": {
                "_id": str(show["_id"]),
                "title": show["title"],
                "image": show["image"],
                "type": "show"
            },
            "seasonNumber": season["seasonNumber"]
        }
        episode_dict["type"] = "episode"  # Add type field
        
        # Get next episode if available
        next_episode = await episode_collection.find_one(
            {
                "seasonId": episode["seasonId"],
                "episodeNumber": episode["episodeNumber"] + 1
            },
            {"_id": 1}  # Only get the ID
        )
        
        # If no next episode in current season, check for next season's first episode
        next_season_episode = None
        if not next_episode:
            next_season = await season_collection.find_one(
                {
                    "showId": season["showId"],
                    "seasonNumber": season["seasonNumber"] + 1
                },
                {"_id": 1}  # Only get the ID
            )
            
            if next_season:
                next_season_episode = await episode_collection.find_one(
                    {
                        "seasonId": next_season["_id"],
                        "episodeNumber": 1
                    },
                    {"_id": 1}  # Only get the ID
                )
        
        next_info = None
        if next_episode:
            next_info = {"episodeId": str(next_episode["_id"])}
        elif next_season_episode:
            next_info = {"episodeId": str(next_season_episode["_id"])}
        
        result = {
            "success": True,
            "data": episode_dict,
            "watchStatus": None,
            "next": next_info
        }
        
        # Get user watch status if user_id provided
        if user_id:
            watch_doc = await user_watch_collection.find_one({
                "userId": user_id,
                "contentType": "episode",
                "contentId": ObjectId(episode_id)
            })
            
            if watch_doc:
                result["watchStatus"] = {
                    "progress": watch_doc.get("progress", 0),
                    "completed": watch_doc.get("completed", False),
                    "lastWatched": watch_doc.get("watchedAt")
                }
        else:
            # Cache the result (only if no user-specific data)
            await set_cache(cache_key, result, 1800)  # Cache for 30 minutes
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_episode_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
      
async def update_episode_watch_status(episode_id: str, user_id: str, progress: float = 0, completed: bool = False):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})
        
        # Check if episode exists
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})
        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})
        
        # Update or create watch status
        from datetime import datetime
        result = await user_watch_collection.update_one(
            {
                "userId": user_id,
                "contentType": "episode",
                "contentId": ObjectId(episode_id)
            },
            {
                "$set": {
                    "progress": progress,
                    "completed": completed,
                    "watchedAt": datetime.now()
                }
            },
            upsert=True
        )
        
        # Get the updated document
        watch_status = await user_watch_collection.find_one({
            "userId": user_id,
            "contentType": "episode",
            "contentId": ObjectId(episode_id)
        })
        
        # Clear user-related caches
        await delete_cache_pattern(f"user:{user_id}:*")
        
        return {
            "success": True,
            "data": {
                "progress": watch_status.get("progress", 0),
                "completed": watch_status.get("completed", False),
                "lastWatched": watch_status.get("watchedAt")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_episode_watch_status: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
