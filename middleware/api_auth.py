from fastapi import Request, HTTPException, Depends
from config import API_KEY
from utils.auth import get_current_user_optional
from starlette.middleware.base import BaseHTTPMiddleware
import re
import time
from collections import defaultdict

# Simple in-memory rate limiter for API key attempts
class APIKeyRateLimiter:
    def __init__(self, max_attempts=5, window_seconds=60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.ip_attempts = defaultdict(list)
        
    def check_rate_limit(self, ip_address):
        """
        Check if IP has exceeded rate limit for API key attempts
        Returns True if rate limited, False otherwise
        """
        now = time.time()
        
        # Keep only attempts within the time window
        self.ip_attempts[ip_address] = [
            timestamp for timestamp in self.ip_attempts[ip_address]
            if now - timestamp < self.window_seconds
        ]
        
        # Check if too many attempts
        if len(self.ip_attempts[ip_address]) >= self.max_attempts:
            return True
            
        # Record this attempt
        self.ip_attempts[ip_address].append(now)
        return False

# Create a global instance
api_key_limiter = APIKeyRateLimiter()

async def verify_api_key(request: Request):
    """Verify API key for admin-only routes"""
    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Unauthorized: API Key missing"}
        )
    
    # Check for rate limiting
    client_ip = request.client.host
    if api_key_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={"success": False, "message": "Too many API key authentication attempts. Please try again later."}
        )
    
    # Check if API key is valid
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Unauthorized: Invalid API Key"}
        )
    
    return True

async def get_admin_user(request: Request):
    """
    Get admin user object from API key.
    Use this for endpoints that need a user object for admin operations.
    """
    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Unauthorized: API Key missing"}
        )
        
    # Check for rate limiting
    client_ip = request.client.host
    if api_key_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={"success": False, "message": "Too many API key authentication attempts. Please try again later."}
        )
    
    # Check if API key is valid
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Unauthorized: Invalid API Key"}
        )
        
    # Return a mock admin user object
    return {"_id": "admin", "username": "admin", "role": "admin", "is_admin": True}

async def get_user_or_admin(request: Request):
    """
    Get either a regular user (from JWT token) or an admin user (from API key).
    Use this for endpoints that should be accessible by both users and admins.
    """
    # First check for API key (admin auth)
    api_key = request.headers.get("x-api-key")
    if api_key:
        # Check for rate limiting only if they're attempting API key auth
        client_ip = request.client.host
        if api_key_limiter.check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail={"success": False, "message": "Too many API key authentication attempts. Please try again later."}
            )
            
        # Verify API key
        if api_key == API_KEY:
            # Return admin user object
            return {"_id": "admin", "username": "admin", "role": "admin", "is_admin": True}
    
    # If not admin, try to get regular user token
    token = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    
    # Call get_current_user_optional with the extracted token
    if token:
        user = await get_current_user_optional(token)
        if user:
            return user
        
    # Neither admin nor user auth is valid
    raise HTTPException(
        status_code=401,
        detail={"success": False, "message": "Authentication required. Please login or provide a valid API key."}
    )

class AdminPathMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle admin API paths that should redirect to user routes.
    This allows admin APIs to use regular user endpoints without duplicating code.
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Define path mappings for admin routes that should access user routes
        # Format: (regex_pattern, replacement)
        self.admin_path_redirects = [
            # Map /api/admin/movies to /api/movies (for GET requests)
            (r"^/api/admin/movies$", "/api/movies"),
            # Map /api/admin/shows to /api/shows (for GET requests)
            (r"^/api/admin/shows$", "/api/shows"),
            # Map /api/admin/shows/{id} to /api/shows/{id} (for GET requests)
            (r"^/api/admin/shows/([^/]+)$", r"/api/shows/\1"),
            # Map /api/admin/movies/{id} to /api/movies/{id} (for GET requests)
            (r"^/api/admin/movies/([^/]+)$", r"/api/movies/\1"),
            # Map /api/admin/auth/me to /api/auth/me
            (r"^/api/admin/auth/me$", "/api/auth/me"),
        ]
    
    async def dispatch(self, request, call_next):
        # Only process GET requests from admin API
        api_key = request.headers.get("x-api-key")
        if request.method == "GET" and api_key and api_key == API_KEY:
            # Check if path matches any of our redirect patterns
            path = request.url.path
            for pattern, replacement in self.admin_path_redirects:
                if re.match(pattern, path):
                    # Rewrite the path
                    new_path = re.sub(pattern, replacement, path)
                    # Update the request scope with the new path
                    request.scope["path"] = new_path
                    # Update the raw_path as well (needed for some ASGI servers)
                    request.scope["raw_path"] = new_path.encode("utf-8")
                    break
        
        # Continue with the request
        response = await call_next(request)
        return response