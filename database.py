from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from bson import ObjectId
import os
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# MongoDB settings
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "odelu")

# Create a MongoDB client
client = AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE_NAME]

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

# Create indexes for better performance
async def create_indexes():
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