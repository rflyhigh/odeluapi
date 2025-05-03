import requests
import logging

logger = logging.getLogger(__name__)

def secure_video_url(url):
    """
    Create a secure token for video URLs, especially m3u8 files
    """
    if not url:
        return url
        
    # Check if this is a player URL with a list parameter
    if "player/?list=" in url:
        # Extract the actual m3u8 URL from the player URL
        url = url.split("player/?list=", 1)[1]
    
    # Check if the URL is an m3u8 file
    if url and (url.endswith('.m3u8') or '.m3u8' in url):
        try:
            # Call the secure video proxy service
            response = requests.post(
                "https://odeluhost.skibiditoilet-9330jk.workers.dev/encrypt",
                json={"url": url},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                # Return the secure token URL
                return data.get("direct_playlist_url")
            else:
                # If there's an error, log it but return the original URL
                logger.error(f"Error securing video URL: {response.text}")
                return url
        except Exception as e:
            # If there's an exception, log it but return the original URL
            logger.error(f"Exception securing video URL: {str(e)}")
            return url
    
    # If it's not an m3u8 file, return the original URL
    return url
            return url
    
    # If it's not an m3u8 file, return the original URL
    return url
