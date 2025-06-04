from fastapi import HTTPException, status
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
import logging

from database import watchlist_collection, movie_collection, show_collection, serialize_doc, get_cache, set_cache, delete_cache, delete_cache_pattern

logger = logging.getLogger(__name__)

async def add_to_watchlist(user_id: str, content_type: str, content_id: str):
    try:
        # Validate content type
        if content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
            
        # Validate ObjectId
        if not ObjectId.is_valid(content_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content ID format"}
            )
            
        # Check if content exists
        if content_type == "movie":
            content = await movie_collection.find_one({"_id": ObjectId(content_id)}, {"_id": 1})
        else:
            content = await show_collection.find_one({"_id": ObjectId(content_id)}, {"_id": 1})
            
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": f"{content_type.capitalize()} not found"}
            )
            
        # Check if already in watchlist
        existing = await watchlist_collection.find_one({
            "userId": user_id,
            "contentType": content_type,
            "contentId": ObjectId(content_id)
        })
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": f"{content_type.capitalize()} already in watchlist"}
            )
            
        # Add to watchlist
        watchlist_item = {
            "userId": user_id,
            "contentType": content_type,
            "contentId": ObjectId(content_id),
            "addedAt": datetime.now()
        }
        
        result = await watchlist_collection.insert_one(watchlist_item)
        
        # Get the created watchlist item
        created_item = await watchlist_collection.find_one({"_id": result.inserted_id})
        
        # Clear user watchlist cache
        await delete_cache(f"user:{user_id}:watchlist")
        
        return {"success": True, "data": serialize_doc(created_item)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_to_watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def remove_from_watchlist(user_id: str, content_type: str, content_id: str):
    try:
        # Validate content type
        if content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
            
        # Validate ObjectId
        if not ObjectId.is_valid(content_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content ID format"}
            )
            
        # Remove from watchlist
        result = await watchlist_collection.delete_one({
            "userId": user_id,
            "contentType": content_type,
            "contentId": ObjectId(content_id)
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": f"{content_type.capitalize()} not found in watchlist"}
            )
            
        # Clear user watchlist cache
        await delete_cache(f"user:{user_id}:watchlist")
        
        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_from_watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_watchlist(user_id: str):
    try:
        # Try to get from cache first
        cache_key = f"user:{user_id}:watchlist"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Get all watchlist items for user
        cursor = watchlist_collection.find({"userId": user_id}).sort("addedAt", -1)
        
        # Build content details
        watchlist = []
        async for item in cursor:
            item = serialize_doc(item)
            content_id = item["contentId"]
            content_type = item["contentType"]
            
            # Get content details with projection
            projection = {"title": 1, "image": 1, "releaseYear": 1, "startYear": 1}
            
            # Get content details
            if content_type == "movie":
                content = await movie_collection.find_one({"_id": ObjectId(content_id)}, projection)
                if content:
                    content = serialize_doc(content)
                    watchlist.append({
                        "id": content_id,
                        "type": "movie",
                        "title": content.get("title", "Unknown Movie"),
                        "image": content.get("image", ""),
                        "year": content.get("releaseYear", ""),
                        "addedAt": item.get("addedAt")
                    })
            else:  # show
                content = await show_collection.find_one({"_id": ObjectId(content_id)}, projection)
                if content:
                    content = serialize_doc(content)
                    watchlist.append({
                        "id": content_id,
                        "type": "show",
                        "title": content.get("title", "Unknown Show"),
                        "image": content.get("image", ""),
                        "year": content.get("startYear", ""),
                        "addedAt": item.get("addedAt")
                    })
        
        result = {"success": True, "data": watchlist}
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def is_in_watchlist(user_id: str, content_type: str, content_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(content_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content ID format"}
            )
            
        # Check if in watchlist
        item = await watchlist_collection.find_one({
            "userId": user_id,
            "contentType": content_type,
            "contentId": ObjectId(content_id)
        }, {"_id": 1})  # Only get the ID
        
        return {"success": True, "data": {"inWatchlist": item is not None}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in is_in_watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_user_watchlist(target_user_id: str):
    """
    Get watchlist for a specific user (for public profile viewing)
    """
    try:
        # Try to get from cache first
        cache_key = f"user:{target_user_id}:public_watchlist"
        cached_data = await get_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Get all watchlist items for user
        cursor = watchlist_collection.find({"userId": target_user_id}).sort("addedAt", -1)
        
        # Build content details
        watchlist = []
        async for item in cursor:
            item = serialize_doc(item)
            content_id = item["contentId"]
            content_type = item["contentType"]
            
            # Get content details with projection
            projection = {"title": 1, "image": 1, "releaseYear": 1, "startYear": 1}
            
            # Get content details
            if content_type == "movie":
                content = await movie_collection.find_one({"_id": ObjectId(content_id)}, projection)
                if content:
                    content = serialize_doc(content)
                    watchlist.append({
                        "id": content_id,
                        "type": "movie",
                        "title": content.get("title", "Unknown Movie"),
                        "image": content.get("image", ""),
                        "year": content.get("releaseYear", ""),
                        "addedAt": item.get("addedAt")
                    })
            else:  # show
                content = await show_collection.find_one({"_id": ObjectId(content_id)}, projection)
                if content:
                    content = serialize_doc(content)
                    watchlist.append({
                        "id": content_id,
                        "type": "show",
                        "title": content.get("title", "Unknown Show"),
                        "image": content.get("image", ""),
                        "year": content.get("startYear", ""),
                        "addedAt": item.get("addedAt")
                    })
        
        result = {"success": True, "data": watchlist}
        
        # Cache the result
        await set_cache(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    except Exception as e:
        logger.error(f"Error in get_user_watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )
