from fastapi import HTTPException, status
from typing import Dict, List, Any
import pytz
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def get_timezone_info():
    """
    Get timezone information including:
    - Current UTC time
    - List of all available timezones
    - Common timezones with their current offsets from UTC
    """
    try:
        # Get current UTC time
        current_utc = datetime.now(pytz.UTC)
        
        # Get all available timezones
        all_timezones = pytz.all_timezones
        
        # Create a list of common timezones with their current UTC offsets
        common_timezones = [
            "UTC",
            "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
            "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Moscow",
            "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Asia/Dubai",
            "Australia/Sydney", "Pacific/Auckland",
            "America/Toronto", "America/New_York", "America/Los_Angeles",
            "America/Mexico_City", "America/Sao_Paulo"
        ]
        
        timezone_data = []
        for tz_name in common_timezones:
            try:
                tz = pytz.timezone(tz_name)
                current_time = current_utc.astimezone(tz)
                offset_seconds = current_time.utcoffset().total_seconds()
                offset_hours = offset_seconds / 3600
                
                # Format offset string (e.g., +05:30, -08:00)
                offset_str = f"{'+' if offset_hours >= 0 else ''}{int(offset_hours):02d}:{int(abs(offset_hours % 1 * 60)):02d}"
                
                timezone_data.append({
                    "name": tz_name,
                    "offset_hours": offset_hours,
                    "offset_string": offset_str,
                    "current_time": current_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "abbreviated_name": current_time.strftime("%Z")
                })
            except Exception as e:
                logger.warning(f"Error processing timezone {tz_name}: {str(e)}")
        
        return {
            "success": True,
            "data": {
                "current_utc": current_utc.strftime("%Y-%m-%dT%H:%M:%S"),
                "common_timezones": timezone_data,
                "all_timezones": all_timezones
            }
        }
    except Exception as e:
        logger.error(f"Error in get_timezone_info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": f"Failed to retrieve timezone information: {str(e)}"}
        ) 