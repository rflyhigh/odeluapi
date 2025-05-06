from fastapi import HTTPException
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import movie_collection, user_watch_collection, serialize_doc, get_cache, set_cache, delete_cache, delete_cache_pattern
from utils.video_security import secure_video_url

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
            query["title"] = {"$regex": search, "$options": "i"}
        
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
        
        # Secure video URLs in links
        if "links" in movie_dict and movie_dict["links"]:
            for link in movie_dict["links"]:
                if 'url' in link:
                    link["url"] = secure_video_url(link["url"])
        
        # Get related movies based on tags (with projection)
        projection = {
            "title": 1, 
            "image": 1, 
            "releaseYear": 1, 
            "tags": 1, 
            "rating": 1
        }
        
        related_cursor = movie_collection.find({
            "_id": {"$ne": ObjectId(movie_id)},
            "tags": {"$in": movie.get("tags", [])}
        }, projection).limit(6)
        
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