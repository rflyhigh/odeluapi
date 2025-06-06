import pytz
from datetime import datetime
import logging
from typing import Dict, Any, Optional, Union, List
import json

logger = logging.getLogger(__name__)

def convert_datetime_to_timezone(
    dt: Optional[Union[datetime, str]], 
    target_timezone: str = "UTC",
    format_string: Optional[str] = None
) -> Optional[Union[datetime, str]]:
    """
    Convert a datetime object or ISO string to the target timezone.
    
    Args:
        dt: The datetime object or ISO string to convert
        target_timezone: The timezone to convert to (e.g., "Asia/Kolkata")
        format_string: If provided, the result will be formatted as a string
        
    Returns:
        Converted datetime object or formatted string, or None if input is None
    """
    if dt is None:
        return None
        
    # If it's a string, parse it to datetime
    if isinstance(dt, str):
        try:
            # Try parsing ISO format with timezone
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            try:
                # Try parsing ISO format without timezone (assume UTC)
                dt = datetime.fromisoformat(dt)
                dt = dt.replace(tzinfo=pytz.UTC)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse datetime string: {dt}")
                return dt  # Return original if parsing fails
    
    # If datetime has no timezone, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
        
    try:
        # Convert to target timezone
        target_tz = pytz.timezone(target_timezone)
        converted_dt = dt.astimezone(target_tz)
        
        # Format if requested
        if format_string:
            return converted_dt.strftime(format_string)
        
        # Always return ISO format string to ensure JSON serialization
        return converted_dt.isoformat()
    except Exception as e:
        logger.warning(f"Error converting timezone: {str(e)}")
        if isinstance(dt, datetime):
            return dt.isoformat()  # Return ISO format on error
        return dt  # Return original on error

def convert_timestamps_in_dict(
    data: Any, 
    timezone: str = "UTC",
    datetime_fields: Optional[List[str]] = None
) -> Any:
    """
    Recursively convert all datetime fields in a dictionary to the specified timezone.
    
    Args:
        data: Dictionary or list to process
        timezone: Target timezone
        datetime_fields: List of field names to look for (if None, uses default list)
        
    Returns:
        Processed data with converted timestamps
    """
    if datetime_fields is None:
        # Default fields that typically contain datetime values
        datetime_fields = [
            "createdAt", "updatedAt", "watchedAt", "releaseDate", 
            "timestamp", "time", "date", "lastUpdated", "lastViewed"
        ]
    
    # Handle None
    if data is None:
        return None
    
    # Handle dictionaries
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Convert datetime fields
            if key in datetime_fields and (isinstance(value, datetime) or isinstance(value, str)):
                result[key] = convert_datetime_to_timezone(value, timezone)
            # Recursively process nested dictionaries and lists
            elif isinstance(value, (dict, list)):
                result[key] = convert_timestamps_in_dict(value, timezone, datetime_fields)
            else:
                result[key] = value
        return result
    
    # Handle lists
    elif isinstance(data, list):
        return [convert_timestamps_in_dict(item, timezone, datetime_fields) for item in data]
    
    # Return other types unchanged
    return data 