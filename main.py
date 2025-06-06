import uvicorn
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import logging
import asyncio
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import traceback
from pydantic import ValidationError

from database import create_indexes, check_redis_connection, CACHE_ENABLED, REDIS_URL, delete_cache_pattern
from routes import movies, shows, admin, user, auth, watchlist, search, comments, reports, popularity
from config import RATE_LIMIT_DEFAULT, COMMENT_CACHE_TTL
from middleware.api_auth import AdminPathMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])

# Background task to clear comment caches periodically
async def clear_comment_caches():
    """Periodically clear comment caches to ensure users see fresh content"""
    while True:
        try:
            logger.info("Running scheduled comment cache clearing")
            # Clear all comment-related caches
            await delete_cache_pattern("comments:*")
            await delete_cache_pattern("comment:*")
            await delete_cache_pattern("comment_tree:*")
            await delete_cache_pattern("user_comments:*")
            logger.info("Comment caches cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing comment caches: {str(e)}")
        
        # Sleep for the comment cache TTL to ensure caches are regularly refreshed
        # We add 30 seconds to avoid hitting the exact expiry time
        await asyncio.sleep(COMMENT_CACHE_TTL + 30)

# Lifespan context manager to replace on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    logger.info("Starting up the application")
    await create_indexes()
    logger.info("Database indexes created")
    await check_redis_connection()
    
    # Start comment cache clearing task
    if CACHE_ENABLED:
        comment_cache_task = asyncio.create_task(clear_comment_caches())
        logger.info("Comment cache clearing background task started")
    
    yield
    
    # Shutdown event
    logger.info("Shutting down the application")
    # Cancel background tasks
    if CACHE_ENABLED:
        comment_cache_task.cancel()
        try:
            await comment_cache_task
        except asyncio.CancelledError:
            logger.info("Comment cache clearing task cancelled")
    
    # Close database connections
    from database import client, redis_client
    client.close()
    if redis_client:
        await redis_client.close()

# Create FastAPI app with ORJSON for faster serialization
app = FastAPI(
    title="Odelu API",
    description="Backend API for Odelu streaming platform",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url=None,  # Disable default docs URL
    redoc_url=None,  # Disable default redoc URL
    openapi_url=None  # Disable OpenAPI schema completely
)

# Add custom error handler for authentication errors
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "message": "Authentication required. Please login to access this content."}
        )
        
    # Extract the detail and format it consistently
    detail = exc.detail
    if isinstance(detail, dict) and "detail" in detail:
        # Already formatted by our controller exception handlers
        return JSONResponse(
            status_code=exc.status_code,
            content=detail
        )
    
    # Generic formatting for standard FastAPI errors
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": str(detail)}
    )

# Add custom error handler for validation errors
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error",
            "errors": error_messages
        }
    )

# Add custom error handler for generic exceptions
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the full traceback for debugging
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())
    
    # Return a generic error message
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An unexpected error occurred. Please try again later."
        }
    )

# Add rate limiter
app.state.limiter = limiter

# Custom handler for rate limit exceeded
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "success": False,
            "message": "Too many requests. Please try again later."
        }
    )

app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Add admin path middleware to handle API route redirections
app.add_middleware(AdminPathMiddleware)

# Include routers
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(shows.router, prefix="/api/shows", tags=["shows"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(comments.router, prefix="/api/comments", tags=["comments"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(popularity.router, prefix="/api/popularity", tags=["popularity"])

# Root endpoint
@app.get("/", tags=["root"])
@limiter.limit("60/minute")
async def root(request: Request):
    return {
        "message": "Odelu API (Python FastAPI)",
        "status": "works :)",
        "endpoints": [
            "/api/movies",
            "/api/shows",
            "/api/user",
            "/api/auth",
            "/api/watchlist",
            "/api/search",
            "/api/comments",
            "/api/reports",
            "/api/popularity"
        ]
    }

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}

# Redis status endpoint
@app.get("/redis-status", tags=["health"])
async def redis_status():
    redis_working = await check_redis_connection()
    return {
        "redis_enabled": CACHE_ENABLED,
        "redis_status": "connected" if redis_working else "disconnected"
    }

# Serve static files if in production
if os.getenv("ENVIRONMENT") == "production":
    # Check if client build directory exists
    build_path = os.path.join(os.getcwd(), "client", "build")
    if os.path.exists(build_path):
        app.mount("/", StaticFiles(directory=build_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", "8000")), 
        reload=True,
        workers=int(os.getenv("WORKERS", "4"))
    )
