from fastapi import HTTPException, status
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo import DESCENDING
import logging
from datetime import datetime, timedelta

from database import (
    content_view_collection, 
    movie_collection, 
    show_collection, 
    serialize_doc,
    get_cache,
    set_cache
)

logger = logging.getLogger(__name__)

async def track_content_view(content_id: str, content_type: str, user_id: Optional[str] = None):
    """
    Track a view for a specific content item
    """
    try:
        # Validate content type
        if content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
            
        # Validate content exists
        content_obj_id = ObjectId(content_id)
        if content_type == "movie":
            content = await movie_collection.find_one({"_id": content_obj_id}, projection={"_id": 1})
        else:
            content = await show_collection.find_one({"_id": content_obj_id}, projection={"_id": 1})
            
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": f"{content_type.capitalize()} not found"}
            )
        
        # Create view record
        view_data = {
            "contentId": content_obj_id,
            "contentType": content_type,
            "timestamp": datetime.now()
        }
        
        # Add user ID if available
        if user_id:
            view_data["userId"] = user_id
            
        # Insert view record
        await content_view_collection.insert_one(view_data)
        
        # Update view count in content document
        collection = movie_collection if content_type == "movie" else show_collection
        await collection.update_one(
            {"_id": content_obj_id},
            {"$inc": {"viewCount": 1}}
        )
        
        return {"success": True, "message": "View tracked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in track_content_view: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_popular_movies(limit: int = 10, time_period: str = "week"):
    """
    Get popular movies based on view count
    """
    try:
        # Try to get from cache first
        cache_key = f"popular:movies:{limit}:{time_period}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
        # Calculate time period
        now = datetime.now()
        if time_period == "day":
            start_date = now - timedelta(days=1)
        elif time_period == "week":
            start_date = now - timedelta(days=7)
        elif time_period == "month":
            start_date = now - timedelta(days=30)
        elif time_period == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = datetime.min  # All time
        
        # Aggregate pipeline to get view counts
        pipeline = [
            {"$match": {
                "contentType": "movie",
                "timestamp": {"$gte": start_date}
            }},
            {"$group": {
                "_id": "$contentId",
                "viewCount": {"$sum": 1}
            }},
            {"$sort": {"viewCount": -1}},
            {"$limit": limit}
        ]
        
        # Execute aggregation
        cursor = content_view_collection.aggregate(pipeline)
        popular_ids = await cursor.to_list(length=limit)
        
        # Get movie details for the popular IDs
        popular_movies = []
        for item in popular_ids:
            movie_id = item["_id"]
            movie = await movie_collection.find_one(
                {"_id": movie_id},
                {"title": 1, "image": 1, "releaseYear": 1, "rating": 1, "viewCount": 1}
            )
            if movie:
                movie_data = serialize_doc(movie)
                movie_data["type"] = "movie"
                movie_data["recentViews"] = item["viewCount"]
                popular_movies.append(movie_data)
        
        # If we don't have enough results from recent views, supplement with overall popular movies
        if len(popular_movies) < limit:
            remaining = limit - len(popular_movies)
            existing_ids = [movie["_id"] for movie in popular_movies]
            
            # Get movies with highest overall viewCount
            cursor = movie_collection.find(
                {"_id": {"$nin": [ObjectId(id) for id in existing_ids]}},
                {"title": 1, "image": 1, "releaseYear": 1, "rating": 1, "viewCount": 1}
            ).sort("viewCount", DESCENDING).limit(remaining)
            
            additional_movies = await cursor.to_list(length=remaining)
            for movie in additional_movies:
                movie_data = serialize_doc(movie)
                movie_data["type"] = "movie"
                movie_data["recentViews"] = movie.get("viewCount", 0)
                popular_movies.append(movie_data)
        
        result = {
            "success": True,
            "data": popular_movies,
            "period": time_period
        }
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_popular_movies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_popular_shows(limit: int = 10, time_period: str = "week"):
    """
    Get popular shows based on view count
    """
    try:
        # Try to get from cache first
        cache_key = f"popular:shows:{limit}:{time_period}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
        # Calculate time period
        now = datetime.now()
        if time_period == "day":
            start_date = now - timedelta(days=1)
        elif time_period == "week":
            start_date = now - timedelta(days=7)
        elif time_period == "month":
            start_date = now - timedelta(days=30)
        elif time_period == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = datetime.min  # All time
        
        # Aggregate pipeline to get view counts
        pipeline = [
            {"$match": {
                "contentType": "show",
                "timestamp": {"$gte": start_date}
            }},
            {"$group": {
                "_id": "$contentId",
                "viewCount": {"$sum": 1}
            }},
            {"$sort": {"viewCount": -1}},
            {"$limit": limit}
        ]
        
        # Execute aggregation
        cursor = content_view_collection.aggregate(pipeline)
        popular_ids = await cursor.to_list(length=limit)
        
        # Get show details for the popular IDs
        popular_shows = []
        for item in popular_ids:
            show_id = item["_id"]
            show = await show_collection.find_one(
                {"_id": show_id},
                {"title": 1, "image": 1, "startYear": 1, "endYear": 1, "rating": 1, "viewCount": 1}
            )
            if show:
                show_data = serialize_doc(show)
                show_data["type"] = "show"
                show_data["recentViews"] = item["viewCount"]
                popular_shows.append(show_data)
        
        # If we don't have enough results from recent views, supplement with overall popular shows
        if len(popular_shows) < limit:
            remaining = limit - len(popular_shows)
            existing_ids = [show["_id"] for show in popular_shows]
            
            # Get shows with highest overall viewCount
            cursor = show_collection.find(
                {"_id": {"$nin": [ObjectId(id) for id in existing_ids]}},
                {"title": 1, "image": 1, "startYear": 1, "endYear": 1, "rating": 1, "viewCount": 1}
            ).sort("viewCount", DESCENDING).limit(remaining)
            
            additional_shows = await cursor.to_list(length=remaining)
            for show in additional_shows:
                show_data = serialize_doc(show)
                show_data["type"] = "show"
                show_data["recentViews"] = show.get("viewCount", 0)
                popular_shows.append(show_data)
        
        result = {
            "success": True,
            "data": popular_shows,
            "period": time_period
        }
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_popular_shows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        ) 