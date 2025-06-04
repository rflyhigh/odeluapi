from fastapi import HTTPException
from typing import List, Optional, Dict
from bson import ObjectId
import logging
import re

from database import movie_collection, show_collection, get_cache, set_cache

logger = logging.getLogger(__name__)

async def get_search_suggestions(query: str, limit: int = 10):
    """
    Get search suggestions for movies and shows based on a query string.
    Returns combined results from collections.
    """
    try:
        if not query or len(query) < 2:
            return {"success": True, "data": []}
        
        # Try to get from cache first
        cache_key = f"search:suggestions:{query}:{limit}"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
        
        # Enhanced regex patterns for better search
        # 1. Match exact start of words (highest priority)
        start_pattern = {"$regex": f"^{re.escape(query)}", "$options": "i"}
        # 2. Match word boundaries (medium priority)
        word_pattern = {"$regex": f"\\b{re.escape(query)}", "$options": "i"}
        # 3. Contains pattern (lowest priority)
        contains_pattern = {"$regex": f"{re.escape(query)}", "$options": "i"}
        
        # Projections
        movie_projection = {"_id": 1, "title": 1, "image": 1, "releaseYear": 1, "tags": 1}
        show_projection = {"_id": 1, "title": 1, "image": 1, "startYear": 1, "tags": 1}
        
        # Proportional distribution of results based on confidence
        high_limit = max(limit // 4, 1)
        med_limit = max(limit // 3, 1)
        low_limit = max(limit // 2, 1)
        
        # Results containers
        high_priority = []
        medium_priority = []
        low_priority = []
        
        # Search in movies collection - Starts with (high priority)
        movie_cursor_high = movie_collection.find(
            {"title": start_pattern}, 
            movie_projection
        ).limit(high_limit)
        
        # Search in shows collection - Starts with (high priority)
        show_cursor_high = show_collection.find(
            {"title": start_pattern}, 
            show_projection
        ).limit(high_limit)
        
        # Gather high priority results
        async for movie in movie_cursor_high:
            high_priority.append({
                "id": str(movie["_id"]),
                "title": movie["title"],
                "image": movie.get("image", ""),
                "year": movie.get("releaseYear", ""),
                "type": "movie",
                "score": 100
            })
            
        async for show in show_cursor_high:
            high_priority.append({
                "id": str(show["_id"]),
                "title": show["title"],
                "image": show.get("image", ""),
                "year": show.get("startYear", ""),
                "type": "show",
                "score": 100
            })
        
        # Medium priority - word boundary
        if len(high_priority) < limit:
            # Exclude already found IDs
            high_ids = [item["id"] for item in high_priority]
            
            # Search for word boundaries
            movie_cursor_med = movie_collection.find(
                {"$and": [
                    {"_id": {"$nin": [ObjectId(id) for id in high_ids if ObjectId.is_valid(id)]}},
                    {"title": word_pattern}
                ]}, 
                movie_projection
            ).limit(med_limit)
            
            show_cursor_med = show_collection.find(
                {"$and": [
                    {"_id": {"$nin": [ObjectId(id) for id in high_ids if ObjectId.is_valid(id)]}},
                    {"title": word_pattern}
                ]}, 
                show_projection
            ).limit(med_limit)
            
            # Gather medium priority results
            async for movie in movie_cursor_med:
                medium_priority.append({
                    "id": str(movie["_id"]),
                    "title": movie["title"],
                    "image": movie.get("image", ""),
                    "year": movie.get("releaseYear", ""),
                    "type": "movie",
                    "score": 70
                })
                
            async for show in show_cursor_med:
                medium_priority.append({
                    "id": str(show["_id"]),
                    "title": show["title"],
                    "image": show.get("image", ""),
                    "year": show.get("startYear", ""),
                    "type": "show",
                    "score": 70
                })
        
        # Low priority - contains anywhere
        if len(high_priority) + len(medium_priority) < limit:
            # Exclude already found IDs
            found_ids = [item["id"] for item in high_priority + medium_priority]
            
            # Search for contains pattern
            movie_cursor_low = movie_collection.find(
                {"$and": [
                    {"_id": {"$nin": [ObjectId(id) for id in found_ids if ObjectId.is_valid(id)]}},
                    {"$or": [
                        {"title": contains_pattern},
                        {"tags": contains_pattern}
                    ]}
                ]}, 
                movie_projection
            ).limit(low_limit)
            
            show_cursor_low = show_collection.find(
                {"$and": [
                    {"_id": {"$nin": [ObjectId(id) for id in found_ids if ObjectId.is_valid(id)]}},
                    {"$or": [
                        {"title": contains_pattern},
                        {"tags": contains_pattern}
                    ]}
                ]}, 
                show_projection
            ).limit(low_limit)
            
            # Gather low priority results
            async for movie in movie_cursor_low:
                title_match = re.search(query, movie["title"], re.IGNORECASE) is not None
                tag_match = any(re.search(query, tag, re.IGNORECASE) for tag in movie.get("tags", []) if isinstance(tag, str))
                
                score = 60 if title_match else 40
                
                low_priority.append({
                    "id": str(movie["_id"]),
                    "title": movie["title"],
                    "image": movie.get("image", ""),
                    "year": movie.get("releaseYear", ""),
                    "type": "movie",
                    "score": score
                })
                
            async for show in show_cursor_low:
                title_match = re.search(query, show["title"], re.IGNORECASE) is not None
                tag_match = any(re.search(query, tag, re.IGNORECASE) for tag in show.get("tags", []) if isinstance(tag, str))
                
                score = 60 if title_match else 40
                
                low_priority.append({
                    "id": str(show["_id"]),
                    "title": show["title"],
                    "image": show.get("image", ""),
                    "year": show.get("startYear", ""),
                    "type": "show",
                    "score": score
                })
        
        # Combine and sort results by score
        results = high_priority + medium_priority + low_priority
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Remove score from final output and limit results
        final_results = []
        for item in results[:limit]:
            item_copy = dict(item)
            if "score" in item_copy:
                del item_copy["score"]
            final_results.append(item_copy)
        
        response = {"success": True, "data": final_results}
        
        # Cache results for a short period
        await set_cache(cache_key, response, 60)  # Cache for 1 minute
        
        return response
    except Exception as e:
        logger.error(f"Error in get_search_suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail={"success": False, "message": str(e)}) 