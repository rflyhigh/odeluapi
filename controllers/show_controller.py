from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import show_collection, season_collection, episode_collection, user_watch_collection, serialize_doc, get_cache, set_cache, delete_cache, delete_cache_pattern
from utils.video_security import secure_video_url

logger = logging.getLogger(__name__)

async def get_all_shows(tag: Optional[str] = None, search: Optional[str] = None, 
                        limit: int = 20, page: int = 1):
    try:
        cache_key = f"shows:list:{tag or 'all'}:{search or 'none'}:{page}:{limit}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        skip = (page - 1) * limit
        
        query = {}
        if tag:
            query["tags"] = tag
        
        if search:
            query["title"] = {"$regex": search, "$options": "i"}
        
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
        
        cursor = show_collection.find(query, projection).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        
        shows = []
        async for show in cursor:
            show_dict = serialize_doc(show)
            show_dict["type"] = "show"
            shows.append(show_dict)
        
        total = await show_collection.count_documents(query)
        
        result = {
            "success": True,
            "data": shows,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit
            }
        }
        
        await set_cache(cache_key, result, 300)
        
        return result
    except Exception as e:
        logger.error(f"Error in get_all_shows: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_featured_shows():
    try:
        cache_key = "shows:featured"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
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
        
        featured_shows = []
        async for show in cursor:
            show_dict = serialize_doc(show)
            show_dict["type"] = "show"
            featured_shows.append(show_dict)
        
        result = {"success": True, "data": featured_shows}
        
        await set_cache(cache_key, result, 600)
        
        return result
    except Exception as e:
        logger.error(f"Error in get_featured_shows: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
    
async def get_show_by_id(show_id: str, user_id: Optional[str] = None):
    try:
        if not ObjectId.is_valid(show_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid show ID format"})
        
        cache_key = f"shows:detail:{show_id}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        show = await show_collection.find_one({"_id": ObjectId(show_id)})
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
        
        seasons_cursor = season_collection.find({"showId": ObjectId(show_id)}).sort("seasonNumber", 1)
        seasons = []
        async for season in seasons_cursor:
            season_dict = serialize_doc(season)
            
            season_dict["episodeCount"] = len(season.get("episodes", []))
            if "episodes" in season_dict:
                del season_dict["episodes"]
            
            seasons.append(season_dict)
        
        show_dict = serialize_doc(show)
        show_dict["seasons"] = seasons
        show_dict["type"] = "show"
        
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
        
        related_shows = []
        async for related in related_cursor:
            related_dict = serialize_doc(related)
            related_dict["type"] = "show"
            related_shows.append(related_dict)
        
        result = {
            "success": True,
            "data": show_dict,
            "related": related_shows,
            "watchHistory": []
        }
        
        if user_id:
            season_ids = [ObjectId(season["_id"]) for season in seasons]
            
            if season_ids:
                first_season_episodes = await episode_collection.find(
                    {"seasonId": season_ids[0]},
                    {"_id": 1}
                ).to_list(length=None)
                
                first_season_episode_ids = [ep["_id"] for ep in first_season_episodes]
                
                if first_season_episode_ids:
                    watch_cursor = user_watch_collection.find({
                        "userId": user_id,
                        "contentType": "episode",
                        "contentId": {"$in": first_season_episode_ids}
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
            await set_cache(cache_key, result, 1800)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_show_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_season_episodes(show_id: str, season_id: str, page: int = 1, limit: int = 10, user_id: Optional[str] = None):
    try:
        if not ObjectId.is_valid(show_id) or not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid ID format"})
        
        cache_key = f"shows:{show_id}:season:{season_id}:episodes:{page}:{limit}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        show = await show_collection.find_one(
            {"_id": ObjectId(show_id)},
            {"title": 1}
        )
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
            
        season = await season_collection.find_one(
            {"_id": ObjectId(season_id), "showId": ObjectId(show_id)},
            {"seasonNumber": 1}
        )
        
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
            
        skip = (page - 1) * limit
        
        episodes_cursor = episode_collection.find(
            {"seasonId": ObjectId(season_id)}
        ).sort("episodeNumber", 1).skip(skip).limit(limit)
        
        total_episodes = await episode_collection.count_documents({"seasonId": ObjectId(season_id)})
        
        episodes = []
        async for episode in episodes_cursor:
            episode_dict = serialize_doc(episode)
            episodes.append(episode_dict)
            
        result = {
            "success": True,
            "data": episodes,
            "pagination": {
                "total": total_episodes,
                "page": page,
                "pages": (total_episodes + limit - 1) // limit,
                "hasMore": (skip + limit) < total_episodes
            },
            "season": {
                "_id": str(season["_id"]),
                "seasonNumber": season["seasonNumber"]
            },
            "show": {
                "_id": str(show["_id"]),
                "title": show["title"]
            }
        }
        
        if user_id and episodes:
            episode_ids = [ObjectId(ep["_id"]) for ep in episodes]
            
            watch_cursor = user_watch_collection.find({
                "userId": user_id,
                "contentType": "episode",
                "contentId": {"$in": episode_ids}
            })
            
            watch_status = {}
            async for watch in watch_cursor:
                watch_status[str(watch["contentId"])] = {
                    "progress": watch.get("progress", 0),
                    "completed": watch.get("completed", False),
                    "lastWatched": watch.get("watchedAt")
                }
                
            result["watchStatus"] = watch_status
        else:
            await set_cache(cache_key, result, 900)
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_season_episodes: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_episode_by_id(episode_id: str, user_id: Optional[str] = None):
    try:
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})
        
        cache_key = f"episodes:detail:{episode_id}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})
        
        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})
        
        season = await season_collection.find_one({"_id": episode["seasonId"]})
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
        
        show_projection = {"title": 1, "image": 1}
        show = await show_collection.find_one({"_id": season["showId"]}, show_projection)
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
        
        episode_dict = serialize_doc(episode)
        
        if "links" in episode_dict and episode_dict["links"]:
            for link in episode_dict["links"]:
                if 'url' in link:
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
        episode_dict["type"] = "episode"
        
        next_episode = await episode_collection.find_one(
            {
                "seasonId": episode["seasonId"],
                "episodeNumber": episode["episodeNumber"] + 1
            },
            {"_id": 1}
        )
        
        next_season_episode = None
        if not next_episode:
            next_season = await season_collection.find_one(
                {
                    "showId": season["showId"],
                    "seasonNumber": season["seasonNumber"] + 1
                },
                {"_id": 1}
            )
            
            if next_season:
                next_season_episode = await episode_collection.find_one(
                    {
                        "seasonId": next_season["_id"],
                        "episodeNumber": 1
                    },
                    {"_id": 1}
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
            await set_cache(cache_key, result, 1800)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_episode_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_all_season_episodes(show_id: str, season_id: str, user_id: Optional[str] = None):
    try:
        if not ObjectId.is_valid(show_id) or not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid ID format"})
        
        cache_key = f"shows:{show_id}:season:{season_id}:all-episodes"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        show = await show_collection.find_one(
            {"_id": ObjectId(show_id)},
            {"title": 1}
        )
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
            
        season = await season_collection.find_one(
            {"_id": ObjectId(season_id), "showId": ObjectId(show_id)},
            {"seasonNumber": 1}
        )
        
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
            
        episodes_cursor = episode_collection.find(
            {"seasonId": ObjectId(season_id)}
        ).sort("episodeNumber", 1)
        
        episodes = []
        async for episode in episodes_cursor:
            episode_dict = serialize_doc(episode)
            episodes.append(episode_dict)
            
        result = {
            "success": True,
            "data": episodes,
            "season": {
                "_id": str(season["_id"]),
                "seasonNumber": season["seasonNumber"]
            },
            "show": {
                "_id": str(show["_id"]),
                "title": show["title"]
            }
        }
        
        if user_id and episodes:
            episode_ids = [ObjectId(ep["_id"]) for ep in episodes]
            
            watch_cursor = user_watch_collection.find({
                "userId": user_id,
                "contentType": "episode",
                "contentId": {"$in": episode_ids}
            })
            
            watch_status = {}
            async for watch in watch_cursor:
                watch_status[str(watch["contentId"])] = {
                    "progress": watch.get("progress", 0),
                    "completed": watch.get("completed", False),
                    "lastWatched": watch.get("watchedAt")
                }
                
            result["watchStatus"] = watch_status
        else:
            await set_cache(cache_key, result, 900)
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_season_episodes: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})
      
async def update_episode_watch_status(episode_id: str, user_id: str, progress: float = 0, completed: bool = False):
    try:
        if not ObjectId.is_valid(episode_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid episode ID format"})
        
        episode = await episode_collection.find_one({"_id": ObjectId(episode_id)})
        if not episode:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Episode not found"})
        
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
        
        watch_status = await user_watch_collection.find_one({
            "userId": user_id,
            "contentType": "episode",
            "contentId": ObjectId(episode_id)
        })
        
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
