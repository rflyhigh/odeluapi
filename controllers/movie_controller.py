from fastapi import HTTPException
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging
import re

from database import movie_collection, user_watch_collection, serialize_doc, get_cache, set_cache, delete_cache, delete_cache_pattern
from utils.video_security import secure_video_url
from utils.time_converter import convert_duration_to_minutes

logger = logging.getLogger(__name__)

async def get_all_movies(tag: Optional[str] = None, search: Optional[str] = None, 
                         limit: int = 20, page: int = 1):
    try:
        # Try to get from cache first
        cache_key = f"movies:list:{tag or 'all'}:{search or 'none'}:{page}:{limit}"
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
            "releaseYear": 1, 
            "tags": 1, 
            "featured": 1,
            "rating": 1,
            "createdAt": 1
        }
        
        # Execute query with pagination and projection
        cursor = movie_collection.find(query, projection).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        
        # Convert to list and add type field
        movies = []
        async for movie in cursor:
            movie_dict = serialize_doc(movie)
            movie_dict["type"] = "movie"  # Add type field
            movies.append(movie_dict)
        
        # Get total count for pagination
        total = await movie_collection.count_documents(query)
        
        result = {
            "success": True,
            "data": movies,
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
        logger.error(f"Error in get_all_movies: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_featured_movies():
    try:
        # Try to get from cache first
        cache_key = "movies:featured"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Find featured movies with projection
        projection = {
            "title": 1, 
            "image": 1, 
            "releaseYear": 1, 
            "tags": 1, 
            "rating": 1,
            "description": 1,
            "coverImage": 1
        }
        
        cursor = movie_collection.find({"featured": True}, projection).limit(10)
        
        # Convert to list and add type field
        featured_movies = []
        async for movie in cursor:
            movie_dict = serialize_doc(movie)
            movie_dict["type"] = "movie"  # Add type field
            featured_movies.append(movie_dict)
        
        result = {"success": True, "data": featured_movies}
        
        # Cache the result
        await set_cache(cache_key, result, 600)  # Cache for 10 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_featured_movies: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_movie_by_id(movie_id: str, user_id: Optional[str] = None):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid movie ID format"})
        
        # Try to get from cache first (without watch status)
        cache_key = f"movies:detail:{movie_id}"
        cached_data = await get_cache(cache_key)
        
        if cached_data and not user_id:
            return cached_data
            
        # Find movie by ID
        movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})
        
        if not movie:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Movie not found"})
        
        # Add type field
        movie_dict = serialize_doc(movie)
        movie_dict["type"] = "movie"
        
        # Convert duration to minutes if it exists
        if "duration" in movie_dict and isinstance(movie_dict["duration"], str):
            minutes = convert_duration_to_minutes(movie_dict["duration"])
            if minutes:
                movie_dict["durationMinutes"] = minutes
        
        # Secure video URLs in links
        if "links" in movie_dict and movie_dict["links"]:
            for link in movie_dict["links"]:
                if 'url' in link:
                    link["url"] = secure_video_url(link["url"])
        
        # Enhanced recommendation system with title similarity and tag priority
        projection = {
            "title": 1, 
            "image": 1, 
            "releaseYear": 1, 
            "tags": 1, 
            "rating": 1
        }
        
        movie_title = movie.get("title", "")
        movie_tags = movie.get("tags", [])
        
        pipeline = [
            # Exclude current movie
            {"$match": {"_id": {"$ne": ObjectId(movie_id)}}},
            
            # Add score field
            {"$addFields": {
                "titleSimilarity": {
                    "$cond": [
                        # Exact match on part of title (highest priority)
                        {"$regexMatch": {
                            "input": {"$toLower": "$title"},
                            "regex": f".*{re.escape(movie_title.lower())}.*"
                        }},
                        100,
                        {"$cond": [
                            # Share at least one word (medium priority)
                            {"$gt": [
                                {"$size": {
                                    "$setIntersection": [
                                        {"$split": [{"$toLower": "$title"}, " "]},
                                        {"$split": [movie_title.lower(), " "]}
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
                                movie_tags
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
        
        related_cursor = movie_collection.aggregate(pipeline)
        
        # Convert to list and add type field
        related_movies = []
        async for related in related_cursor:
            related_dict = serialize_doc(related)
            related_dict["type"] = "movie"  # Add type field
            related_movies.append(related_dict)
        
        result = {
            "success": True,
            "data": movie_dict,
            "related": related_movies,
            "watchStatus": None
        }
        
        # Get watch status if user_id provided
        if user_id:
            watch_doc = await user_watch_collection.find_one({
                "userId": user_id,
                "contentType": "movie",
                "contentId": ObjectId(movie_id)
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
        logger.error(f"Error in get_movie_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def update_watch_status(movie_id: str, user_id: str, progress: float = 0, completed: bool = False):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid movie ID format"})
        
        # Check if movie exists
        movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Movie not found"})
        
        # Update or create watch status
        from datetime import datetime
        result = await user_watch_collection.update_one(
            {
                "userId": user_id,
                "contentType": "movie",
                "contentId": ObjectId(movie_id)
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
            "contentType": "movie",
            "contentId": ObjectId(movie_id)
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
        logger.error(f"Error in update_watch_status: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})