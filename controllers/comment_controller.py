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

def decode_html_entities(content: str) -> str:
    """
    Decode HTML entities back to their original characters
    """
    return html.unescape(content)

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
        
        # Get total count for pagination
        total_count = await comment_collection.count_documents(query)
        
        # Get comments with pagination
        comments_cursor = comment_collection.find(query, projection=projection)
        comments_cursor.sort("createdAt", -1)  # Sort by newest first
        comments_cursor.skip(skip).limit(limit)
        
        comments = await comments_cursor.to_list(length=limit)
        
        # Process comments
        result = []
        for comment in comments:
            # Decode HTML entities in comment content
            if "content" in comment:
                comment["content"] = decode_html_entities(comment["content"])
            
            # Add avatar if missing
            if "avatar" not in comment or comment["avatar"] is None:
                user = await user_collection.find_one(
                    {"_id": comment["user_id"]}, 
                    projection={"avatar": 1}
                )
                if user and "avatar" in user:
                    comment["avatar"] = user["avatar"]
                else:
                    comment["avatar"] = None
                    
            # Add to result
            result.append(serialize_doc(comment))
        
        # Return with pagination info
        return {
            "success": True,
            "data": result,
            "pagination": {
                "total": total_count,
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
    """
    Get a specific comment by ID
    """
    try:
        # Find comment
        comment = await comment_collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Comment not found"}
            )
            
        # Decode HTML entities in comment content
        if "content" in comment:
            comment["content"] = decode_html_entities(comment["content"])
            
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
            
        # Decode HTML entities in comment content
        if "content" in comment:
            comment["content"] = decode_html_entities(comment["content"])
            
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
            
            # Process each reply
            for reply in all_replies:
                # Decode HTML entities in reply content
                if "content" in reply:
                    reply["content"] = decode_html_entities(reply["content"])
                
                # Add avatar if missing
                if "avatar" not in reply:
                    user = await user_collection.find_one(
                        {"_id": reply["user_id"]}, 
                        projection={"avatar": 1}
                    )
                    if user and "avatar" in user:
                        reply["avatar"] = user["avatar"]
                    else:
                        reply["avatar"] = None
            
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
    Get all comments made by a specific user
    """
    try:
        # Validate user exists
        user = await user_collection.find_one({"_id": ObjectId(user_id)}, projection={"_id": 1, "username": 1, "avatar": 1})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "User not found"}
            )
        
        # Build query
        query = {"user_id": ObjectId(user_id)}
        
        # Get total count for pagination
        total_count = await comment_collection.count_documents(query)
        
        # Get comments with pagination
        comments_cursor = comment_collection.find(query)
        comments_cursor.sort("createdAt", -1)  # Sort by newest first
        comments_cursor.skip(skip).limit(limit)
        
        comments = await comments_cursor.to_list(length=limit)
        
        # Process comments
        result = []
        for comment in comments:
            # Decode HTML entities in comment content
            if "content" in comment:
                comment["content"] = decode_html_entities(comment["content"])
                
            # Add content details (movie/show title)
            content_type = comment.get("content_type", "")
            content_id = comment.get("content_id", "")
            
            if content_type and content_id:
                if content_type == "movie":
                    content = await movie_collection.find_one(
                        {"_id": content_id},
                        projection={"title": 1, "poster_path": 1}
                    )
                    if content:
                        comment["content_title"] = content.get("title", "Unknown Movie")
                        comment["content_poster"] = content.get("poster_path", "")
                else:
                    content = await show_collection.find_one(
                        {"_id": content_id},
                        projection={"name": 1, "poster_path": 1}
                    )
                    if content:
                        comment["content_title"] = content.get("name", "Unknown Show")
                        comment["content_poster"] = content.get("poster_path", "")
            
            # Add to result
            result.append(serialize_doc(comment))
        
        # Return with pagination info
        return {
            "success": True,
            "data": {
                "user": {
                    "_id": str(user["_id"]),
                    "username": user.get("username", ""),
                    "avatar": user.get("avatar", "")
                },
                "comments": result,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "skip": skip
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

async def fix_comment_html_entities():
    """
    Fix existing comments in the database by decoding HTML entities
    This is an admin-only function
    """
    try:
        # Get all comments
        comments_cursor = comment_collection.find({})
        comments = await comments_cursor.to_list(length=None)
        
        fixed_count = 0
        
        # Process each comment
        for comment in comments:
            if "content" in comment:
                # Decode HTML entities in content
                decoded_content = decode_html_entities(comment["content"])
                
                # Update if different
                if decoded_content != comment["content"]:
                    await comment_collection.update_one(
                        {"_id": comment["_id"]},
                        {"$set": {"content": decoded_content}}
                    )
                    fixed_count += 1
        
        # Clear all comment caches
        await delete_cache_pattern("comments:*")
        await delete_cache_pattern("comment:*")
        await delete_cache_pattern("comment_tree:*")
        await delete_cache_pattern("user_comments:*")
        
        return {"success": True, "message": f"Fixed {fixed_count} comments with HTML entities"}
    
    except Exception as e:
        logger.error(f"Error in fix_comment_html_entities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        ) 
