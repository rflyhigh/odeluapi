from fastapi import HTTPException
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import show_collection, season_collection, episode_collection, user_watch_collection, serialize_doc
from utils.video_security import secure_video_url

logger = logging.getLogger(__name__)

async def get_all_shows(tag: Optional[str] = None, search: Optional[str] = None, 
                        limit: int = 20, page: int = 1):
    try:
        skip = (page - 1) * limit
        
        # Build query
        query = {}
        if tag:
            query["tags"] = tag
        
        if search:
            query["title"] = {"$regex": search, "$options": "i"}
        
        # Execute query with pagination
        cursor = show_collection.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        
        # Convert to list and add type field
        shows = []
        async for show in cursor:
            show_dict = serialize_doc(show)
            show_dict["type"] = "show"  # Add type field
            shows.append(show_dict)
        
        # Get total count for pagination
        total = await show_collection.count_documents(query)
        
        return {
            "success": True,
            "data": shows,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except Exception as e:
        logger.error(f"Error in get_all_shows: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_featured_shows():
    try:
        # Find featured shows
        cursor = show_collection.find({"featured": True}).limit(10)
        
        # Convert to list and add type field
        featured_shows = []
        async for show in cursor:
            show_dict = serialize_doc(show)
            show_dict["type"] = "show"  # Add type field
            featured_shows.append(show_dict)
        
        return {"success": True, "data": featured_shows}
    except Exception as e:
        logger.error(f"Error in get_featured_shows: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
    
async def get_show_by_id(show_id: str, user_id: Optional[str] = None):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})
        
        # Find show by ID
        show = await show_collection.find_one({"_id": ObjectId(show_id)})
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
        
        # Get seasons for this show
        seasons_cursor = season_collection.find({"showId": ObjectId(show_id)}).sort("seasonNumber", 1)
        seasons = []
        async for season in seasons_cursor:
            season_dict = serialize_doc(season)
            
            # Get episodes for this season
            episodes_cursor = episode_collection.find({"seasonId": season["_id"]}).sort("episodeNumber", 1)
            episodes = []
            async for episode in episodes_cursor:
                episode_dict = serialize_doc(episode)
                
                # Secure video URLs in links
                if "links" in episode_dict and episode_dict["links"]:
                    for link in episode_dict["links"]:
                        link["url"] = secure_video_url(link["url"])
                
                episodes.append(episode_dict)
            
            season_dict["episodes"] = episodes
            seasons.append(season_dict)
        
        # Add seasons to show
        show_dict = serialize_doc(show)
        show_dict["seasons"] = seasons
        show_dict["type"] = "show"  # Add type field
        
        # Get related shows based on tags
        related_cursor = show_collection.find({
            "_id": {"$ne": ObjectId(show_id)},
            "tags": {"$in": show.get("tags", [])}
        }).limit(6)
        
        # Convert to list and add type field
        related_shows = []
        async for related in related_cursor:
            related_dict = serialize_doc(related)
            related_dict["type"] = "show"  # Add type field
            related_shows.append(related_dict)
        
        # Get user watch history if user_id provided
        watch_history = []
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
                
                async for watch in watch_cursor:
                    watch_history.append({
                        "episodeId": str(watch["contentId"]),
                        "progress": watch.get("progress", 0),
                        "completed": watch.get("completed", False),
                        "lastWatched": watch.get("watchedAt")
                    })
        
        return {
            "success": True,
            "data": show_dict,
            "related": related_shows,
            "watchHistory": watch_history
        }
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
        
        # Find episode by ID
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})
        
        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})
        
        # Get season info
        season = await season_collection.find_one({"_id": episode["seasonId"]})
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
        
        # Get show info
        show = await show_collection.find_one({"_id": season["showId"]})
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
        
        # Build response object
        episode_dict = serialize_doc(episode)
        
        # Secure video URLs in links
        if "links" in episode_dict and episode_dict["links"]:
            for link in episode_dict["links"]:
                link["url"] = secure_video_url(link["url"])
        
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
        
        # Get user watch status if user_id provided
        watch_status = None
        if user_id:
            watch_doc = await user_watch_collection.find_one({
                "userId": user_id,
                "contentType": "episode",
                "contentId": ObjectId(episode_id)
            })
            
            if watch_doc:
                watch_status = {
                    "progress": watch_doc.get("progress", 0),
                    "completed": watch_doc.get("completed", False),
                    "lastWatched": watch_doc.get("watchedAt")
                }
        
        # Get next episode if available
        next_episode = await episode_collection.find_one({
            "seasonId": episode["seasonId"],
            "episodeNumber": episode["episodeNumber"] + 1
        })
        
        # If no next episode in current season, check for next season's first episode
        next_season_episode = None
        if not next_episode:
            next_season = await season_collection.find_one({
                "showId": season["showId"],
                "seasonNumber": season["seasonNumber"] + 1
            })
            
            if next_season:
                next_season_episode = await episode_collection.find_one({
                    "seasonId": next_season["_id"],
                    "episodeNumber": 1
                })
        
        next_info = None
        if next_episode:
            next_info = {"episodeId": str(next_episode["_id"])}
        elif next_season_episode:
            next_info = {"episodeId": str(next_season_episode["_id"])}
        
        return {
            "success": True,
            "data": episode_dict,
            "watchStatus": watch_status,
            "next": next_info
        }
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
