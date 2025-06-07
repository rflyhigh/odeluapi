from fastapi import HTTPException, status, Depends
from typing import Optional, List
import logging
from bson import ObjectId
from datetime import datetime
import asyncio
import html
import re

from database import comment_collection, user_collection, movie_collection, show_collection, serialize_doc, delete_cache_pattern
from models.comment import CommentCreate, Comment
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

def sanitize_comment_content(content: str) -> str:
    """
    Sanitize comment content to prevent XSS attacks
    - Escape HTML entities
    - Remove potentially malicious patterns
    """
    # Escape HTML entities
    sanitized = html.escape(content)
    
    # Strip potentially harmful patterns
    patterns = [
        r'javascript:',
        r'data:text/html',
        r'expression\s*\(',
        r'vbscript:',
    ]
    
    for pattern in patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    return sanitized

async def create_comment(comment_data: CommentCreate, current_user: dict):
    """
    Create a new comment on a movie or show.
    Only authenticated users can create comments.
    """
    try:
        # Validate content type
        if comment_data.content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
            
        # Validate content exists
        content_id = ObjectId(comment_data.content_id)
        if comment_data.content_type == "movie":
            content = await movie_collection.find_one({"_id": content_id}, projection={"_id": 1})
        else:
            content = await show_collection.find_one({"_id": content_id}, projection={"_id": 1})
            
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": f"{comment_data.content_type.capitalize()} not found"}
            )
        
        # If this is a reply, validate parent comment exists
        parent = None
        if comment_data.parent_id:
            parent_id = ObjectId(comment_data.parent_id)
            parent = await comment_collection.find_one(
                {"_id": parent_id},
                projection={"_id": 1, "content_id": 1, "content_type": 1, "parent_id": 1, "nesting_level": 1}
            )
            
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"success": False, "message": "Parent comment not found"}
                )
                
            # Ensure parent comment is for the same content
            if str(parent["content_id"]) != comment_data.content_id or parent["content_type"] != comment_data.content_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "message": "Parent comment must be for the same content"}
                )
                
            # Check nesting level - max 5 levels of nesting
            nesting_level = parent.get("nesting_level", 1) + 1
            if nesting_level > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "message": "Maximum comment nesting level reached (5)"}
                )
        else:
            nesting_level = 1  # Top level comment
        
        # Sanitize comment content to prevent XSS
        sanitized_content = sanitize_comment_content(comment_data.content)
        
        # Create comment document
        now = datetime.now()
        comment_dict = {
            "content": sanitized_content,
            "user_id": ObjectId(current_user["_id"]),
            "username": current_user["username"],
            "avatar": current_user.get("avatar", None),  # Include user avatar if available
            "content_id": content_id,
            "content_type": comment_data.content_type,
            "replies": [],
            "nesting_level": nesting_level,
            "createdAt": now,
            "updatedAt": now
        }
        
        # Add parent_id if this is a reply
        if comment_data.parent_id:
            comment_dict["parent_id"] = ObjectId(comment_data.parent_id)
        
        # Insert comment and update parent's replies in a transaction or bulk write
        # for better performance
        tasks = []
        
        # Task 1: Insert the new comment
        result = await comment_collection.insert_one(comment_dict)
        
        # Task 2: If this is a reply, update parent's replies list
        if comment_data.parent_id:
            await comment_collection.update_one(
                {"_id": ObjectId(comment_data.parent_id)},
                {"$push": {"replies": result.inserted_id}}
            )
        
        # Get created comment
        created_comment = await comment_collection.find_one({"_id": result.inserted_id})
        
        # Clear cache for this content's comments - always clear on new comment creation
        # to ensure users see fresh comments
        cache_patterns = [
            f"comments:{comment_data.content_type}:{comment_data.content_id}:*"
        ]
        
        # If this is a reply, also clear the parent comment's cache
        if comment_data.parent_id:
            cache_patterns.extend([
                f"comment:{comment_data.parent_id}",
                f"comment_tree:{comment_data.parent_id}"
            ])
            
        # Clear all relevant caches
        for pattern in cache_patterns:
            await delete_cache_pattern(pattern)
        
        return {"success": True, "data": serialize_doc(created_comment)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_comment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_comments(content_id: str, content_type: str, parent_id: Optional[str] = None, limit: int = 50, skip: int = 0):
    """
    Get comments for a movie or show.
    Can be filtered by parent_id to get only top-level comments or replies to a specific comment.
    """
    try:
        # Validate content type
        if content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
            
        # Validate content exists (use projection to only get _id field for performance)
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
            
        # Build query
        query = {
            "content_id": content_obj_id,
            "content_type": content_type
        }
        
        # Filter by parent_id
        if parent_id is None:
            # Get top-level comments (no parent)
            query["parent_id"] = {"$exists": False}
        else:
            # Get replies to a specific comment
            query["parent_id"] = ObjectId(parent_id)
            
        # Optimize projection to return only needed fields
        projection = {
            "_id": 1,
            "content": 1,
            "user_id": 1,
            "username": 1,
            "avatar": 1,
            "createdAt": 1,
            "updatedAt": 1,
            "replies": 1,
            "parent_id": 1
        }
            
        # Get comments and total count in parallel for better performance
        comments_future = comment_collection.find(query, projection).sort("createdAt", -1).skip(skip).limit(limit).to_list(length=limit)
        total_future = comment_collection.count_documents(query)
        
        # Execute both database operations concurrently
        comments, total = await asyncio.gather(comments_future, total_future)
        
        # Process avatars and fetch replies for each comment
        for comment in comments:
            # Add avatar if missing
            if "avatar" not in comment:
                user = await user_collection.find_one(
                    {"_id": comment["user_id"]}, 
                    projection={"avatar": 1}
                )
                if user and "avatar" in user:
                    comment["avatar"] = user["avatar"]
                else:
                    comment["avatar"] = None
            
            # Fetch replies if this is a top-level comment
            if "replies" in comment and comment["replies"]:
                reply_ids = [ObjectId(r) for r in comment["replies"]]
                replies = await comment_collection.find(
                    {"_id": {"$in": reply_ids}},
                    projection=projection
                ).to_list(length=len(reply_ids))
                
                # Process avatars for replies
                for reply in replies:
                    if "avatar" not in reply:
                        user = await user_collection.find_one(
                            {"_id": reply["user_id"]}, 
                            projection={"avatar": 1}
                        )
                        if user and "avatar" in user:
                            reply["avatar"] = user["avatar"]
                        else:
                            reply["avatar"] = None
                
                # Sort replies by creation date
                replies.sort(key=lambda x: x["createdAt"], reverse=True)
                comment["replies"] = replies
        
        return {
            "success": True,
            "data": {
                "comments": serialize_doc(comments),
                "total": total,
                "limit": limit,
                "skip": skip
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_comments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_comment_by_id(comment_id: str):
    """Get a specific comment by ID"""
    try:
        comment = await comment_collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Comment not found"}
            )
            
        return {"success": True, "data": serialize_doc(comment)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_comment_by_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def update_comment(comment_id: str, content: str, current_user: dict):
    """
    Update a comment.
    Only the comment owner can update it.
    """
    try:
        # Find comment
        comment = await comment_collection.find_one(
            {"_id": ObjectId(comment_id)}, 
            projection={"_id": 1, "user_id": 1, "content_type": 1, "content_id": 1}
        )
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Comment not found"}
            )
            
        # Check if user is the comment owner
        if str(comment["user_id"]) != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"success": False, "message": "You can only update your own comments"}
            )
            
        # Sanitize comment content to prevent XSS
        sanitized_content = sanitize_comment_content(content)
            
        # Update comment
        await comment_collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": {"content": sanitized_content, "updatedAt": datetime.now()}}
        )
        
        # Get updated comment
        updated_comment = await comment_collection.find_one({"_id": ObjectId(comment_id)})
        
        # Clear caches
        cache_keys = [
            f"comments:{comment['content_type']}:{comment['content_id']}:*",  # Content comments
            f"comment:{comment_id}",  # Individual comment
            f"comment_tree:*",  # Any comment trees that might include this
            f"user_comments:{current_user['_id']}:*"  # User's comments
        ]
        
        for key in cache_keys:
            await delete_cache_pattern(key)
        
        return {"success": True, "data": serialize_doc(updated_comment)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_comment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def delete_comment(comment_id: str, current_user: dict):
    """
    Delete a comment.
    Only the comment owner or admin can delete it.
    """
    try:
        # Find comment
        comment = await comment_collection.find_one(
            {"_id": ObjectId(comment_id)},
            projection={"_id": 1, "user_id": 1, "content_type": 1, "content_id": 1, "parent_id": 1, "replies": 1}
        )
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Comment not found"}
            )
            
        # Check if user is the comment owner or admin
        if str(comment["user_id"]) != str(current_user["_id"]) and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"success": False, "message": "You can only delete your own comments"}
            )
        
        # Store cache keys to clear later
        cache_keys = [
            f"comments:{comment['content_type']}:{comment['content_id']}:*",  # Content comments
            f"comment:{comment_id}",  # Individual comment
            f"comment_tree:*",  # Any comment trees that might include this
            f"user_comments:{comment['user_id']}:*"  # User's comments
        ]
        
        # Recursively delete all replies and their children
        await delete_comment_recursively(ObjectId(comment_id), cache_keys)
            
        # If this is a reply, update the parent's replies list
        if "parent_id" in comment:
            await comment_collection.update_one(
                {"_id": comment["parent_id"]},
                {"$pull": {"replies": ObjectId(comment_id)}}
            )
            
            # Add parent comment cache to clear
            parent = await comment_collection.find_one(
                {"_id": comment["parent_id"]},
                projection={"_id": 1}
            )
            if parent:
                cache_keys.append(f"comment:{parent['_id']}")
                cache_keys.append(f"comment_tree:{parent['_id']}")
        
        # Clear all relevant caches
        for key in set(cache_keys):  # Using set to remove duplicates
            await delete_cache_pattern(key)
        
        return {"success": True, "message": "Comment deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_comment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def delete_comment_recursively(comment_id: ObjectId, cache_keys: list):
    """
    Recursively delete a comment and all its descendants
    """
    try:
        # Get comment info
        comment = await comment_collection.find_one(
            {"_id": comment_id},
            projection={"_id": 1, "user_id": 1, "replies": 1}
        )
        
        if comment:
            # Add user's cache to clear
            if "user_id" in comment:
                cache_keys.append(f"user_comments:{comment['user_id']}:*")
            
            # Process replies recursively before deleting this comment
            if "replies" in comment and comment["replies"]:
                for reply_id in comment["replies"]:
                    await delete_comment_recursively(reply_id, cache_keys)
            
            # Delete the comment after processing its children
            await comment_collection.delete_one({"_id": comment_id})
            return True
        return False
    
    except Exception as e:
        logger.error(f"Error in delete_comment_recursively: {str(e)}")
        return False

async def get_comment_tree(comment_id: str):
    """
    Get a comment and all its nested replies as a tree structure.
    """
    try:
        # Find comment
        comment = await comment_collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Comment not found"}
            )
            
        # Add avatar if missing
        if "avatar" not in comment:
            user = await user_collection.find_one(
                {"_id": comment["user_id"]}, 
                projection={"avatar": 1}
            )
            if user and "avatar" in user:
                comment["avatar"] = user["avatar"]
            else:
                comment["avatar"] = None
            
        # Convert to serialized format
        result = serialize_doc(comment)
        
        # If it has replies, get them more efficiently with a single query
        if "replies" in comment and comment["replies"]:
            # Skip empty arrays
            if not comment["replies"]:
                result["replies"] = []
                return {"success": True, "data": result}
                
            # Get all replies in a single query
            reply_ids = [ObjectId(r) for r in comment["replies"]]
            replies_cursor = comment_collection.find({"_id": {"$in": reply_ids}})
            all_replies = await replies_cursor.to_list(length=len(reply_ids))
            
            # Create a lookup map
            replies_map = {str(r["_id"]): r for r in all_replies}
            
            # Get all user IDs that need avatars
            user_ids = []
            for reply in all_replies:
                if "avatar" not in reply:
                    user_ids.append(reply["user_id"])
            
            # Get avatars in a single query if needed
            if user_ids:
                users = await user_collection.find(
                    {"_id": {"$in": user_ids}}, 
                    projection={"_id": 1, "avatar": 1}
                ).to_list(length=len(user_ids))
                
                # Create lookup dictionary
                user_avatars = {str(user["_id"]): user.get("avatar") for user in users}
                
                # Add avatars to replies
                for reply in all_replies:
                    if "avatar" not in reply:
                        reply["avatar"] = user_avatars.get(str(reply["user_id"]))
            
            # Process replies
            processed_replies = []
            for reply_id in comment["replies"]:
                reply_obj = replies_map.get(str(reply_id))
                if reply_obj:
                    # Check if this reply has nested replies
                    if "replies" in reply_obj and reply_obj["replies"]:
                        # Process nested replies recursively
                        reply_result = await get_comment_tree(str(reply_id))
                        processed_replies.append(reply_result["data"])
                    else:
                        # No nested replies
                        processed_replies.append(serialize_doc(reply_obj))
            
            result["replies"] = processed_replies
        else:
            result["replies"] = []
            
        return {"success": True, "data": result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_comment_tree: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_user_comments(user_id: str, limit: int = 50, skip: int = 0):
    """
    Get all comments made by a specific user.
    """
    try:
        # Validate user exists
        user_obj_id = ObjectId(user_id)
        user = await user_collection.find_one(
            {"_id": user_obj_id},
            projection={"_id": 1, "username": 1, "avatar": 1}
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "User not found"}
            )
            
        # Query all comments by this user
        query = {"user_id": user_obj_id}
        
        # Optimize projection to return only needed fields
        projection = {
            "_id": 1,
            "content": 1,
            "content_id": 1,
            "content_type": 1,
            "parent_id": 1,
            "createdAt": 1,
            "updatedAt": 1,
            "replies": 1
        }
        
        # Run queries in parallel for better performance
        comments_future = comment_collection.find(query, projection).sort("createdAt", -1).skip(skip).limit(limit).to_list(length=limit)
        total_future = comment_collection.count_documents(query)
        
        # Execute both database operations concurrently
        comments, total = await asyncio.gather(comments_future, total_future)
        
        # Add user info to all comments to avoid additional lookups
        avatar = user.get("avatar", None)
        username = user.get("username", "")
        
        for comment in comments:
            comment["avatar"] = avatar
            comment["username"] = username
        
        return {
            "success": True,
            "data": {
                "comments": serialize_doc(comments),
                "total": total,
                "limit": limit,
                "skip": skip,
                "user": {
                    "id": str(user["_id"]),
                    "username": username,
                    "avatar": avatar
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_comments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        ) 
