import requests
import logging
import re
import os
from urllib.parse import unquote, urlparse, parse_qs
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
ADDITIONAL_ENCRYPTION_KEY = os.getenv('ADDITIONAL_ENCRYPTION_KEY')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def secure_video_url(url):
    """
    Create a secure token for video URLs, especially m3u8 files
    Handles various player URL formats and extracts the actual m3u8 URL
    Never returns raw m3u8 URLs to the user for security reasons
    """
    if not url:
        logger.warning("Empty URL provided to secure_video_url")
        raise ValueError("Empty URL provided. Please provide a valid player URL.")
        
    # Log the original URL for debugging
    logger.debug(f"Processing URL: {url}")
    
    # Keep track of the original URL to return in case of errors
    original_url = url
    extracted_url = None
    
    # STEP 1: Try to extract m3u8 URL from various player formats
    
    # Case 1: player/?list= format (interflew.github.io)
    if "player/?list=" in url:
        extracted_url = url.split("player/?list=", 1)[1]
        logger.debug(f"Extracted URL from player/?list= format: {extracted_url}")
    
    # Case 2: player?list= format (without slash) (odelugit.github.io)
    elif "player?list=" in url:
        extracted_url = url.split("player?list=", 1)[1]
        logger.debug(f"Extracted URL from player?list= format: {extracted_url}")
    
    # Case 3: Generic player with URL parameter handling
    # This handles URLs like player.php?url=, player?src=, etc.
    elif "/player" in url or "player." in url:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # Look for common URL parameter names
        for param in ['list', 'url', 'src', 'source', 'video', 'm3u8', 'hls', 'stream']:
            if param in query_params and query_params[param]:
                potential_url = query_params[param][0]
                if "http" in potential_url:
                    extracted_url = potential_url
                    logger.debug(f"Extracted URL from player {param} parameter: {extracted_url}")
                    break
    
    # STEP 2: If we've extracted a URL from a player, use it for further processing
    working_url = extracted_url if extracted_url else url
    
    # STEP 3: Handle GitHub raw URLs and other hosting services
    
    # Case 1: Special handling for GitHub raw URLs
    github_patterns = [
        # Raw GitHub URL detection with various formats
        r'(https?://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/.*?\.m3u8)',
        # User content GitHub URLs
        r'(https?://[^/]*?\.github\.io/[^/]*?/.*?\.m3u8)',
        # GitHub pages URL
        r'(https?://[^/]*?\.github\.io/.*?\.m3u8)'
    ]
    
    for pattern in github_patterns:
        github_match = re.search(pattern, working_url)
        if github_match:
            extracted_url = github_match.group(1)
            working_url = unquote(extracted_url)
            logger.debug(f"Extracted GitHub raw URL: {working_url}")
            break
    
    # STEP 4: Generic m3u8 URL extraction (fallback)
    if not extracted_url or '.m3u8' not in working_url:
        # Look for any URL that ends with .m3u8 or contains .m3u8 in the path
        m3u8_pattern = re.compile(r'(https?://[^\s"\']+\.m3u8(?:[^\s"\']*)?)')
        m3u8_match = m3u8_pattern.search(working_url)
        
        if m3u8_match:
            # Use the matched m3u8 URL
            extracted_url = m3u8_match.group(1)
            # Sometimes the URL might be URL-encoded
            working_url = unquote(extracted_url)
            logger.debug(f"Extracted m3u8 URL from generic pattern: {working_url}")
    
    # Ensure we have a proper URL to work with, default to original if all extraction attempts failed
    final_url = working_url if working_url and ("http" in working_url and '.m3u8' in working_url) else original_url
    
    # STEP 5: Finally check if the URL is definitely an m3u8 file and secure it
    if '.m3u8' in final_url:
        try:
            # Call the secure video proxy service
            logger.info(f"Securing m3u8 URL: {final_url[:50]}...")  # Log partial URL for privacy
            
            # Check if we should use additional encryption
            use_additional_encryption = ADDITIONAL_ENCRYPTION_KEY is not None and ADDITIONAL_ENCRYPTION_KEY.strip() != ''
            logger.info(f"Additional encryption enabled: {use_additional_encryption}")
            
            # Prepare request data
            request_data = {
                "url": final_url,
                "useAdditionalEncryption": use_additional_encryption
            }
            
            # Add optional title if available
            if 'title' in locals() and title:
                request_data["title"] = title
            
            response = requests.post(
                "https://v1.m3u8lock.workers.dev/encrypt",
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=10  # Increased timeout for reliability
            )
            
            if response.status_code == 200:
                data = response.json()
                secured_url = data.get("direct_playlist_url")
                if not secured_url:
                    logger.error(f"No direct_playlist_url in response: {data}")
                    raise SecurityError("Failed to secure video URL. For security reasons, raw m3u8 URLs cannot be processed.")
                
                # Log the response for debugging
                logger.debug(f"URL secured successfully, additional encryption: {data.get('additional_encryption', False)}")
                return secured_url
            else:
                # If there's an error, raise exception - never return raw m3u8
                logger.error(f"Error securing video URL: {response.status_code} - {response.text}")
                raise SecurityError(f"Failed to secure video URL (HTTP {response.status_code}). For security reasons, raw m3u8 URLs cannot be returned.")
        except Exception as e:
            # If there's an exception, log it and raise a security error
            logger.error(f"Exception securing video URL: {str(e)}")
            raise SecurityError("Failed to secure video URL. For security reasons, raw m3u8 URLs cannot be processed.")
    
    # If it doesn't appear to be an m3u8 file or we couldn't extract one, return the player URL
    # This is acceptable as player URLs don't expose the raw stream
    if '.m3u8' not in original_url:
        logger.debug(f"URL is not an m3u8 file, returning original player URL")
        return original_url
    else:
        # If the original URL contains m3u8, we should not return it
        raise SecurityError("Unable to secure the provided URL. For security reasons, raw m3u8 URLs cannot be returned.")


class SecurityError(Exception):
    """Exception raised for security issues when handling m3u8 URLs."""
    pass
