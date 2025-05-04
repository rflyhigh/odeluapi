import requests
import logging

logger = logging.getLogger(__name__)

def secure_video_url(url):
    """
    Create a secure token for video URLs, especially m3u8 files
    """
    if not url:
        logger.warning(f"Empty URL provided to secure_video_url")
        return url
        
    # Log the original URL for debugging
    logger.debug(f"Processing URL: {url}")
    
    # Check if this is a player URL with a list parameter
    if "player/?list=" in url:
        # Extract the actual m3u8 URL from the player URL
        url = url.split("player/?list=", 1)[1]
        logger.debug(f"Extracted URL from player: {url}")
    
    # Check if the URL is an m3u8 file
    if url and (url.endswith('.m3u8') or '.m3u8' in url):
        try:
            # Call the secure video proxy service
            logger.info(f"Securing m3u8 URL: {url[:50]}...")  # Log partial URL for privacy
            response = requests.post(
                "https://v1.m3u8lock.workers.dev/encrypt",
                json={"url": url},
                headers={"Content-Type": "application/json"},
                timeout=5  # Add timeout to prevent hanging
            )
            
            if response.status_code == 200:
                data = response.json()
                secured_url = data.get("direct_playlist_url")
                if not secured_url:
                    logger.error(f"No direct_playlist_url in response: {data}")
                    return url
                logger.debug(f"URL secured successfully")
                return secured_url
            else:
                # If there's an error, log it but return the original URL
                logger.error(f"Error securing video URL: {response.status_code} - {response.text}")
                return url
        except Exception as e:
            # If there's an exception, log it but return the original URL
            logger.error(f"Exception securing video URL: {str(e)}")
            return url
    
    # If it's not an m3u8 file, return the original URL
    logger.debug(f"URL is not an m3u8 file, returning original")
    return url
