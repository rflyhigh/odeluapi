import httpx
from fastapi import HTTPException, status
import logging
from config import TURNSTILE_SECRET_KEY, TURNSTILE_VERIFY_URL

logger = logging.getLogger(__name__)

async def verify_turnstile_token(token: str, ip_address: str = None) -> bool:
    """
    Verify a Cloudflare Turnstile token.
    
    Args:
        token: The Turnstile token to verify
        ip_address: The IP address of the client (optional)
        
    Returns:
        bool: True if verification is successful, raises HTTPException otherwise
    """
    try:
        # Prepare verification data
        data = {
            "secret": TURNSTILE_SECRET_KEY,
            "response": token
        }
        
        # Add the IP address if provided
        if ip_address:
            data["remoteip"] = ip_address
            
        # Make request to Cloudflare to verify the token
        async with httpx.AsyncClient() as client:
            response = await client.post(TURNSTILE_VERIFY_URL, data=data)
            
        # Parse response
        result = response.json()
        
        # Check if verification was successful
        if not result.get("success", False):
            error_codes = result.get("error-codes", [])
            logger.warning(f"Turnstile verification failed: {error_codes}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "CAPTCHA verification failed. Please try again."}
            )
            
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying Turnstile token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": "Failed to verify CAPTCHA. Please try again."}
        ) 