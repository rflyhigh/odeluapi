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
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
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
        # Use orjson for faster serialization
        serialized_data = orjson.dumps(data)
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
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")