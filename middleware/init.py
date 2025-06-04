# Import middleware for easier access
from middleware.api_auth import verify_api_key
from middleware.user_tracker import get_user_id
from middleware.auth_required import require_auth