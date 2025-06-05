from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, StreamingResponse
import json
import logging
import orjson
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from utils.auth import get_current_user_optional
from utils.time_helpers import convert_timestamps_in_dict

logger = logging.getLogger(__name__)

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class TimezoneConverterMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically converts UTC timestamps in responses to the user's preferred timezone.
    This middleware only processes JSON responses and only specific endpoints that need timezone conversion.
    """
    
    def __init__(
        self, 
        app,
        paths_to_process: Optional[list] = None
    ):
        super().__init__(app)
        # Paths that should have timezone conversion applied
        self.paths_to_process = paths_to_process or [
            "/api/comments",
            "/api/user/history",
            "/api/user/continue-watching",
            "/api/user/recently-added",
            "/api/user/me/comments",
            "/api/popularity",  # Adding popularity endpoints
            "/api/watchlist"    # Adding watchlist endpoints
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if this path should be processed
        should_process = False
        for path in self.paths_to_process:
            if request.url.path.startswith(path):
                should_process = True
                break
                
        # Skip processing if path not in list
        if not should_process:
            return await call_next(request)
        
        # Get user's timezone preference
        user_timezone = "UTC"  # Default
        try:
            # Try to get user from token if available
            token = request.headers.get("authorization", "").replace("Bearer ", "")
            if token:
                user = await get_current_user_optional(token)
                if user and "timezone" in user and user["timezone"]:
                    user_timezone = user["timezone"]
                    
            # Check for timezone override in query params
            query_timezone = request.query_params.get("timezone")
            if query_timezone:
                user_timezone = query_timezone
        except Exception as e:
            logger.warning(f"Error getting user timezone: {str(e)}")
        
        # Process the request normally
        response = await call_next(request)
        
        # Only process JSON responses
        if (hasattr(response, "headers") and 
            response.headers.get("content-type", "").startswith("application/json")):
            
            try:
                # Get the response body
                response_body = [chunk async for chunk in response.body_iterator]
                
                # Join and parse the response
                body = b"".join(response_body)
                
                try:
                    # Try parsing with orjson first (faster and handles datetime better)
                    data = orjson.loads(body)
                except Exception:
                    # Fall back to standard json
                    data = json.loads(body.decode("utf-8"))
                
                # Apply timezone conversion to response data
                if "data" in data:
                    data["data"] = convert_timestamps_in_dict(data["data"], user_timezone)
                
                # Convert back to JSON and return as a new response
                try:
                    # Try with orjson first (faster)
                    json_bytes = orjson.dumps(data)
                    
                    # Create a new response with the modified body
                    # Use StreamingResponse to avoid Content-Length issues
                    async def streaming_response():
                        yield json_bytes
                        
                    return StreamingResponse(
                        streaming_response(),
                        status_code=response.status_code,
                        media_type="application/json"
                    )
                except Exception as e:
                    # Fall back to standard json
                    logger.warning(f"orjson serialization failed: {str(e)}")
                    return JSONResponse(
                        content=data,
                        status_code=response.status_code
                    )
            except Exception as e:
                # Log the specific error for debugging
                logger.error(f"Error in timezone middleware: {str(e)}")
                
                # Return original response on error
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
        
        # Return original response for non-JSON responses
        return response 