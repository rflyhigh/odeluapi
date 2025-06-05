from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import json
import logging
import orjson
from typing import Optional, Callable, Dict, Any

from utils.auth import get_current_user_optional
from utils.time_helpers import convert_timestamps_in_dict

logger = logging.getLogger(__name__)

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
            "/api/user/me/comments"
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
                response.body_iterator = iter(response_body)
                
                # Join and parse the response
                body = b"".join(response_body)
                data = json.loads(body.decode("utf-8"))
                
                # Apply timezone conversion to response data
                if "data" in data:
                    data["data"] = convert_timestamps_in_dict(data["data"], user_timezone)
                
                # Return modified response
                return JSONResponse(
                    status_code=response.status_code,
                    content=data,
                    headers=dict(response.headers)
                )
            except Exception as e:
                # If any error occurs, return the original response
                logger.error(f"Error in timezone middleware: {str(e)}")
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
        
        # Return original response for non-JSON responses
        return response 