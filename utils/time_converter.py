import re

def convert_duration_to_minutes(duration_str):
    """
    Convert duration strings like "1h 31min", "90min", "2h", etc. to minutes (integer)
    
    Args:
        duration_str (str): Duration string in format like "1h 31min"
        
    Returns:
        int: Total minutes, or None if parsing fails
    """
    if not duration_str or not isinstance(duration_str, str):
        return None
        
    # Clean up the string
    duration_str = duration_str.lower().strip()
    
    # Initialize total minutes
    total_minutes = 0
    
    # Extract hours
    hours_match = re.search(r'(\d+)\s*h', duration_str)
    if hours_match:
        total_minutes += int(hours_match.group(1)) * 60
    
    # Extract minutes
    minutes_match = re.search(r'(\d+)\s*min', duration_str)
    if minutes_match:
        total_minutes += int(minutes_match.group(1))
    
    # If only a number is provided, assume it's minutes
    if not hours_match and not minutes_match:
        # Try to extract just a number
        number_match = re.search(r'^(\d+)$', duration_str)
        if number_match:
            total_minutes = int(number_match.group(1))
    
    return total_minutes if total_minutes > 0 else None 