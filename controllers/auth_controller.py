from fastapi import HTTPException, status, Depends, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Optional
import logging
from bson import ObjectId
import re

from database import user_collection, serialize_doc, delete_cache_pattern
from models.user import UserCreate, User, UserInDB
from utils.auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)

def sanitize_username(username: str) -> str:
    """
    Sanitize and validate username to prevent security vulnerabilities.
    - Only allow alphanumeric characters, underscores, and hyphens
    - Enforce length restrictions (3-30 characters)
    - Remove any potentially malicious patterns
    
    Raises HTTPException if username is invalid
    Returns the sanitized username
    """
    # Check length
    if not username or len(username) < 3 or len(username) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Username must be between 3 and 30 characters"}
        )
    
    # Check for valid characters
    if not re.match(r'^[a-zA-Z0-9_\-]+$', username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Username can only contain letters, numbers, underscores and hyphens"}
        )
    
    # Prevent common NoSQL injection patterns
    if re.search(r'^\$|\.|\{|\}|;|javascript:|<script|<\/script>|<|>|\"|\\\|\/\*|\*\/', username, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Username contains invalid characters"}
        )
    
    return username

async def register_user(user_data: UserCreate):
    try:
        # Sanitize username
        sanitized_username = sanitize_username(user_data.username)
        user_data.username = sanitized_username
        
        # Check if username already exists
        existing_user = await user_collection.find_one({"username": user_data.username})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Username already registered"}
            )
            
        # Check if email already exists
        existing_email = await user_collection.find_one({"email": user_data.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Email already registered"}
            )
        
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Create new user document
        user_dict = user_data.model_dump(exclude={"password"})
        user_dict["hashed_password"] = hashed_password
        user_dict["watchlist"] = []
        user_dict["createdAt"] = datetime.now()
        user_dict["updatedAt"] = datetime.now()
        # Set default avatar
        user_dict["avatar"] = "default.jpeg"
        
        # Insert into database
        result = await user_collection.insert_one(user_dict)
        
        # Get the created user
        created_user = await user_collection.find_one({"_id": result.inserted_id})
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_data.username},
            expires_delta=access_token_expires
        )
        
        # Return user data and token
        user_data = serialize_doc(created_user)
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return {
            "success": True,
            "data": {
                "user": user_data,
                "access_token": access_token,
                "token_type": "bearer"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in register_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def login_user(form_data: OAuth2PasswordRequestForm):
    try:
        # Sanitize username
        sanitized_username = sanitize_username(form_data.username)
        
        # Find user by username
        user = await user_collection.find_one({"username": sanitized_username})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "message": "Incorrect username or password"}
            )
            
        # Verify password
        if not verify_password(form_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "message": "Incorrect username or password"}
            )
            
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": sanitized_username},
            expires_delta=access_token_expires
        )
        
        # Return token and user data
        user_data = serialize_doc(user)
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return {
            "success": True,
            "data": {
                "access_token": access_token,
                "token_type": "bearer",
                "user": user_data
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in login_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_user_profile(user_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid user ID format"}
            )
            
        # Find user by ID
        user = await user_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "User not found"}
            )
            
        # Return user data (excluding sensitive info)
        user_data = serialize_doc(user)
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return {"success": True, "data": user_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def update_user_profile(user_id: str, user_data: dict):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid user ID format"}
            )
            
        # Check if user exists
        user = await user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "User not found"}
            )
            
        # Sanitize username if it's being updated
        if "username" in user_data:
            # If username is changing, check if new username already exists
            if user_data["username"] != user["username"]:
                sanitized_username = sanitize_username(user_data["username"])
                user_data["username"] = sanitized_username
                
                # Check if username already exists
                existing_user = await user_collection.find_one({"username": sanitized_username})
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"success": False, "message": "Username already taken"}
                    )
            
        # Add updated timestamp
        user_data["updatedAt"] = datetime.now()
        
        # Update user
        await user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": user_data}
        )
        
        # Get updated user
        updated_user = await user_collection.find_one({"_id": ObjectId(user_id)})
        
        # Clear user cache
        await delete_cache_pattern(f"user:{user_id}:*")
        
        # Return updated user data (excluding sensitive info)
        user_data = serialize_doc(updated_user)
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return {"success": True, "data": user_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_user_profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )
    
async def get_user_by_username(username: str):
    try:
        # Sanitize username
        sanitized_username = sanitize_username(username)
        
        # Find user by username
        user = await user_collection.find_one({"username": sanitized_username})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "User not found"}
            )
            
        # Return user data (excluding sensitive info)
        user_data = serialize_doc(user)
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return {"success": True, "data": user_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_by_username: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )
