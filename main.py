import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from starlette.staticfiles import StaticFiles
import os
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from database import create_indexes
from routes import movies, shows, admin, user, auth, watchlist
from config import RATE_LIMIT_DEFAULT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])

# Create FastAPI app with ORJSON for faster serialization
app = FastAPI(
    title="Odelu API",
    description="Backend API for Odelu streaming platform",
    version="1.0.0",
    default_response_class=ORJSONResponse
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(shows.router, prefix="/api/shows", tags=["shows"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])

# Root endpoint
@app.get("/", tags=["root"])
@limiter.limit("60/minute")
async def root(request: Request):
    return {
        "message": "Odelu API Server (Python FastAPI)",
        "status": "running",
        "endpoints": [
            "/api/movies",
            "/api/shows",
            "/api/user",
            "/api/auth",
            "/api/watchlist"
        ]
    }

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the application")
    await create_indexes()
    logger.info("Database indexes created")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down the application")
    # Close database connections
    from database import client, redis_client
    client.close()
    if redis_client:
        await redis_client.close()

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
