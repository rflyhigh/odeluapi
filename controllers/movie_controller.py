from fastapi import HTTPException
from typing import List, Optional
from bson import ObjectId
from pymongo import DESCENDING
import logging

from database import movie_collection, user_watch_collection, serialize_doc

logger = logging.getLogger(__name__)

async def get_all_movies(tag: Optional[str] = None, search: Optional[str] = None, 
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
        cursor = movie_collection.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        
        # Convert to list and add type field
        movies = []
        async for movie in cursor:
            movie_dict = serialize_doc(movie)
            movie_dict["type"] = "movie"  # Add type field
            movies.append(movie_dict)
        
        # Get total count for pagination
        total = await movie_collection.count_documents(query)
        
        return {
            "success": True,
            "data": movies,
            "pagination": {
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except Exception as e:
        logger.error(f"Error in get_all_movies: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_featured_movies():
    try:
        # Find featured movies
        cursor = movie_collection.find({"featured": True}).limit(10)
        
        # Convert to list and add type field
        featured_movies = []
        async for movie in cursor:
            movie_dict = serialize_doc(movie)
            movie_dict["type"] = "movie"  # Add type field
            featured_movies.append(movie_dict)
        
        return {"success": True, "data": featured_movies}
    except Exception as e:
        logger.error(f"Error in get_featured_movies: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)})

async def get_movie_by_id(movie_id: str, user_id: Optional[str] = None):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail={"success": False, "message": "Invalid movie ID format"})
        
        # Find movie by ID
        movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})
        
        if not movie:
            raise HTTPException(status_code=404, detail={"success": False, "message": "Movie not found"})
        
        # Add type field
        movie_dict = serialize_doc(movie)
        movie_dict["type"] = "movie"
        
        # Get related movies based on tags
        related_cursor = movie_collection.find({
            "_id": {"$ne": ObjectId(movie_id)},
            "tags": {"$in": movie.get("tags", [])}
        }).limit(6)
        
        # Convert to list and add type field
        related_movies = []
        async for related in related_cursor:
            related_dict = serialize_doc(related)
            related_dict["type"] = "movie"  # Add type field
            related_movies.append(related_dict)
        
        # Get watch status if user_id provided
        watch_status = None
        if user_id:
            watch_doc = await user_watch_collection.find_one({
                "userId": user_id,
                "contentType": "movie",
                "contentId": ObjectId(movie_id)
            })
            
            if watch_doc:
                watch_status = {
                    "progress": watch_doc.get("progress", 0),
                    "completed": watch_doc.get("completed", False),
                    "lastWatched": watch_doc.get("watchedAt")
                }
        
        return {
            "success": True,
            "data": movie_dict,
            "related": related_movies,
            "watchStatus": watch_status
        }
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