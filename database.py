from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from bson import ObjectId
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import redis.asyncio as redis
import logging
import orjson

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# MongoDB settings
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "odelu")
MAX_POOL_SIZE = int(os.getenv("MONGODB_MAX_POOL_SIZE", "100"))
MIN_POOL_SIZE = int(os.getenv("MONGODB_MIN_POOL_SIZE", "10"))

# Redis settings
REDIS_URL = os.getenv("REDIS_URL", "")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # Default 1 hour
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"

# Create a MongoDB client with connection pooling
client = AsyncIOMotorClient(
    MONGODB_URI,
    maxPoolSize=MAX_POOL_SIZE,
    minPoolSize=MIN_POOL_SIZE,
    retryWrites=True,
    serverSelectionTimeoutMS=5000
)
db = client[DATABASE_NAME]

# Initialize Redis client for caching
redis_client = None
if CACHE_ENABLED:
    try:
        redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=False)
        logger.info("Redis cache initialized successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {str(e)}. Continuing without caching.")

# Collections
movie_collection = db.movies
show_collection = db.shows
season_collection = db.seasons
episode_collection = db.episodes
user_watch_collection = db.user_watches
user_collection = db.users
watchlist_collection = db.watchlists
comment_collection = db.comments
report_collection = db.reports
content_view_collection = db.content_views

# Helper function to convert string ID to ObjectId
def to_object_id(id_str):
    if isinstance(id_str, str) and ObjectId.is_valid(id_str):
        return ObjectId(id_str)
    return id_str

# Helper function to serialize MongoDB documents
def serialize_doc(doc):
    if doc is None:
        return None
        
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
        
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
        
    if isinstance(doc, ObjectId):
        return str(doc)
        
    if isinstance(doc, datetime):
        return doc.isoformat()
        
    return doc

# Cache functions with improved error handling and performance
async def get_cache(key):
    """Get data from cache with improved error handling"""
    if not CACHE_ENABLED or not redis_client:
        return None
    try:
        data = await redis_client.get(key)
        if data:
            return orjson.loads(data)
        return None
    except Exception as e:
        logger.warning(f"Cache get error: {str(e)}")
        return None

async def set_cache(key, data, ttl=CACHE_TTL):
    """Set data in cache with improved serialization"""
    if not CACHE_ENABLED or not redis_client:
        return
    try:
        # Use orjson for faster serialization with options for datetime handling
        serialized_data = orjson.dumps(
            data, 
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_SERIALIZE_DATACLASS
        )
        await redis_client.set(key, serialized_data, ex=ttl)
    except Exception as e:
        logger.warning(f"Cache set error: {str(e)}")

async def delete_cache(key):
    """Delete data from cache"""
    if not CACHE_ENABLED or not redis_client:
        return
    try:
        await redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete error: {str(e)}")

async def delete_cache_pattern(pattern):
    """Delete all keys matching pattern with improved error handling"""
    if not CACHE_ENABLED or not redis_client:
        return
    try:
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache delete pattern error: {str(e)}")

# Create indexes for better performance
async def create_indexes():
    try:
        # Movie indexes
        await movie_collection.create_index([("title", ASCENDING)])
        await movie_collection.create_index([("tags", ASCENDING)])
        await movie_collection.create_index([("featured", ASCENDING)])
        
        # Show indexes
        await show_collection.create_index([("title", ASCENDING)])
        await show_collection.create_index([("tags", ASCENDING)])
        await show_collection.create_index([("featured", ASCENDING)])
        
        # Season indexes
        await season_collection.create_index([("showId", ASCENDING)])
        await season_collection.create_index([("showId", ASCENDING), ("seasonNumber", ASCENDING)], unique=True)
        
        # Episode indexes
        await episode_collection.create_index([("seasonId", ASCENDING)])
        await episode_collection.create_index([("seasonId", ASCENDING), ("episodeNumber", ASCENDING)], unique=True)
        
        # UserWatch indexes
        await user_watch_collection.create_index([("userId", ASCENDING)])
        await user_watch_collection.create_index([("userId", ASCENDING), ("contentType", ASCENDING), ("contentId", ASCENDING)], unique=True)
        await user_watch_collection.create_index([("userId", ASCENDING), ("watchedAt", DESCENDING)])
        
        # User indexes
        await user_collection.create_index([("username", ASCENDING)], unique=True)
        await user_collection.create_index([("email", ASCENDING)], unique=True)
        
        # Watchlist indexes
        await watchlist_collection.create_index([("userId", ASCENDING)])
        await watchlist_collection.create_index([("userId", ASCENDING), ("contentType", ASCENDING), ("contentId", ASCENDING)], unique=True)
        
        # Comment indexes
        await comment_collection.create_index([("content_id", ASCENDING), ("content_type", ASCENDING)])
        await comment_collection.create_index([("user_id", ASCENDING)])
        await comment_collection.create_index([("parent_id", ASCENDING)])
        await comment_collection.create_index([("createdAt", DESCENDING)])
        
        # Report indexes
        await report_collection.create_index([("userId", ASCENDING)])
        await report_collection.create_index([("createdAt", DESCENDING)])
        
        # ContentView indexes
        await content_view_collection.create_index([("userId", ASCENDING)])
        await content_view_collection.create_index([("contentId", ASCENDING)])
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")

# Function to check Redis connection
async def check_redis_connection():
    """Check if Redis connection is working properly"""
    if not CACHE_ENABLED:
        logger.info("Redis cache is disabled")
        return False
    
    if not redis_client:
        logger.warning("Redis client is not initialized")
        return False
        
    try:
        # Try to ping Redis server
        await redis_client.ping()
        logger.info("Redis connection is working properly")
        return True
    except Exception as e:
        logger.error(f"Redis connection check failed: {str(e)}")
        return False

# Utility function for comment operations
async def batch_fetch_user_avatars(comments_list):
    """
    Efficiently fetch avatars for a list of comments in a single database query.
    
    Args:
        comments_list: List of comment objects with user_id fields
        
    Returns:
        The same list with avatar fields populated
    """
    if not comments_list:
        return comments_list
        
    # Collect user IDs that need avatars
    user_ids = []
    avatar_needed_comments = []
    
    for comment in comments_list:
        if "avatar" not in comment or comment["avatar"] is None:
            user_ids.append(comment["user_id"])
            avatar_needed_comments.append(comment)
    
    # Skip if no avatars needed
    if not user_ids:
        return comments_list
    
    try:
        # Fetch all avatars in a single query
        users = await user_collection.find(
            {"_id": {"$in": user_ids}},
            projection={"_id": 1, "avatar": 1}
        ).to_list(length=len(user_ids))
        
        # Create lookup map for fast access
        avatar_map = {str(user["_id"]): user.get("avatar") for user in users}
        
        # Update comments with avatars
        for comment in avatar_needed_comments:
            comment["avatar"] = avatar_map.get(str(comment["user_id"]))
            
        return comments_list
    except Exception as e:
        logger.error(f"Error in batch_fetch_user_avatars: {str(e)}")
        # Return original list on error
        return comments_list