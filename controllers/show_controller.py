from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo import DESCENDING
import logging
import re

from database import show_collection, season_collection, episode_collection, user_watch_collection, serialize_doc, get_cache, set_cache, delete_cache, delete_cache_pattern
from utils.video_security import secure_video_url
from utils.time_converter import convert_duration_to_minutes

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
            # Enhanced search that matches partial words
            search_regex = {"$regex": f"{re.escape(search)}", "$options": "i"}
            query["$or"] = [
                {"title": search_regex},
                {"tags": search_regex},
                {"description": search_regex}
            ]
        
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
            
            # Only include essential season data, not all episodes
            season_dict["episodeCount"] = len(season.get("episodes", []))
            # Remove the full episodes array to reduce payload size
            if "episodes" in season_dict:
                del season_dict["episodes"]
            
            seasons.append(season_dict)
        
        # Add seasons to show
        show_dict = serialize_doc(show)
        show_dict["seasons"] = seasons
        show_dict["type"] = "show"  # Add type field
        
        # Enhanced recommendation system with title similarity and tag priority
        projection = {
            "title": 1, 
            "image": 1, 
            "startYear": 1, 
            "tags": 1, 
            "rating": 1
        }
        
        show_title = show.get("title", "")
        show_tags = show.get("tags", [])
        
        pipeline = [
            # Exclude current show
            {"$match": {"_id": {"$ne": ObjectId(show_id)}}},
            
            # Add score field
            {"$addFields": {
                "titleSimilarity": {
                    "$cond": [
                        # Exact match on part of title (highest priority)
                        {"$regexMatch": {
                            "input": {"$toLower": "$title"},
                            "regex": f".*{re.escape(show_title.lower())}.*"
                        }},
                        100,
                        {"$cond": [
                            # Share at least one word (medium priority)
                            {"$gt": [
                                {"$size": {
                                    "$setIntersection": [
                                        {"$split": [{"$toLower": "$title"}, " "]},
                                        {"$split": [show_title.lower(), " "]}
                                    ]
                                }},
                                0
                            ]},
                            70,
                            # No title similarity
                            0
                        ]}
                    ]
                },
                
                # Tag similarity - more matching tags = higher score
                "tagOverlap": {
                    "$cond": [
                        {"$isArray": "$tags"},
                        {"$size": {
                            "$setIntersection": [
                                {"$ifNull": ["$tags", []]},
                                show_tags
                            ]
                        }},
                        0
                    ]
                },
                
                # Tag count for calculating percentage
                "tagCount": {
                    "$cond": [
                        {"$isArray": "$tags"},
                        {"$size": {"$ifNull": ["$tags", []]}},
                        0
                    ]
                }
            }},
            
            # Calculate final score
            {"$addFields": {
                "score": {
                    "$add": [
                        "$titleSimilarity",
                        # Tag score: (matching tags / total tags) * 50
                        {"$multiply": [
                            {"$cond": [
                                {"$eq": ["$tagCount", 0]},
                                0,
                                {"$divide": ["$tagOverlap", "$tagCount"]}
                            ]},
                            50
                        ]},
                        # Rating bonus
                        {"$multiply": [
                            {"$ifNull": ["$rating", 0]},
                            3
                        ]}
                    ]
                }
            }},
            
            # Sort by score descending
            {"$sort": {"score": -1}},
            
            # Limit results
            {"$limit": 6},
            
            # Project fields to return (exclude scoring fields)
            {"$project": projection}
        ]
        
        related_cursor = show_collection.aggregate(pipeline)
        
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
            # Get all episode IDs from the show's seasons
            season_ids = [ObjectId(season["_id"]) for season in seasons]
            
            # Find episodes for the first season only to avoid loading everything
            if season_ids:
                first_season_episodes = await episode_collection.find(
                    {"seasonId": season_ids[0]},
                    {"_id": 1}  # Only get IDs
                ).to_list(length=None)
                
                first_season_episode_ids = [ep["_id"] for ep in first_season_episodes]
                
                if first_season_episode_ids:
                    # Get watch status for first season episodes
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
            # Cache the result (only if no user-specific data)
            await set_cache(cache_key, result, 1800)  # Cache for 30 minutes
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_show_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_season_episodes(show_id: str, season_id: str, page: int = 1, limit: int = 10, user_id: Optional[str] = None):
    """Get paginated episodes for a specific season"""
    try:
        # Validate ObjectIds
        if not ObjectId.is_valid(show_id) or not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid ID format"})
        
        # Try to get from cache first
        cache_key = f"shows:{show_id}:season:{season_id}:episodes:{page}:{limit}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        # Verify show exists
        show = await show_collection.find_one(
            {"_id": ObjectId(show_id)},
            {"title": 1}  # Only get title
        )
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
            
        # Verify season exists and belongs to show
        season = await season_collection.find_one(
            {"_id": ObjectId(season_id), "showId": ObjectId(show_id)},
            {"seasonNumber": 1}  # Only get season number
        )
        
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
            
        # Calculate pagination
        skip = (page - 1) * limit
        
        # Get episodes with pagination
        episodes_cursor = episode_collection.find(
            {"seasonId": ObjectId(season_id)}
        ).sort("episodeNumber", 1).skip(skip).limit(limit)
        
        # Get total episode count for pagination
        total_episodes = await episode_collection.count_documents({"seasonId": ObjectId(season_id)})
        
        # Process episodes
        episodes = []
        async for episode in episodes_cursor:
            episode_dict = serialize_doc(episode)
            
            # Convert duration to minutes if it exists
            if "duration" in episode_dict and isinstance(episode_dict["duration"], str):
                minutes = convert_duration_to_minutes(episode_dict["duration"])
                if minutes:
                    episode_dict["durationMinutes"] = minutes
                    
            episodes.append(episode_dict)
            
        result = {
            "success": True,
            "data": episodes,
            "pagination": {
                "total": total_episodes,
                "page": page,
                "pages": (total_episodes + limit - 1) // limit,  # Ceiling division
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
        
        # Get watch status if user_id provided
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
            # Cache the result (only if no user-specific data)
            await set_cache(cache_key, result, 900)  # Cache for 15 minutes
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_season_episodes: {str(e)}")
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
        
        # Convert duration to minutes if it exists
        if "duration" in episode_dict and isinstance(episode_dict["duration"], str):
            minutes = convert_duration_to_minutes(episode_dict["duration"])
            if minutes:
                episode_dict["durationMinutes"] = minutes
        
        # Secure video URLs in links
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

async def get_all_season_episodes(show_id: str, season_id: str, user_id: Optional[str] = None):
    """Get all episodes for a specific season without pagination"""
    try:
        # Validate ObjectIds
        if not ObjectId.is_valid(show_id) or not ObjectId.is_valid(season_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid ID format"})
        
        # Try to get from cache first
        cache_key = f"shows:{show_id}:season:{season_id}:all-episodes"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        # Verify show exists
        show = await show_collection.find_one(
            {"_id": ObjectId(show_id)},
            {"title": 1}  # Only get title
        )
        
        if not show:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Show not found"})
            
        # Verify season exists and belongs to show
        season = await season_collection.find_one(
            {"_id": ObjectId(season_id), "showId": ObjectId(show_id)},
            {"seasonNumber": 1}  # Only get season number
        )
        
        if not season:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Season not found"})
            
        # Get all episodes without pagination
        episodes_cursor = episode_collection.find(
            {"seasonId": ObjectId(season_id)}
        ).sort("episodeNumber", 1)
        
        # Process episodes
        episodes = []
        async for episode in episodes_cursor:
            episode_dict = serialize_doc(episode)
            
            # Convert duration to minutes if it exists
            if "duration" in episode_dict and isinstance(episode_dict["duration"], str):
                minutes = convert_duration_to_minutes(episode_dict["duration"])
                if minutes:
                    episode_dict["durationMinutes"] = minutes
                    
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
        
        # Get watch status if user_id provided
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
            # Cache the result (only if no user-specific data)
            await set_cache(cache_key, result, 900)  # Cache for 15 minutes
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_season_episodes: {str(e)}")
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
