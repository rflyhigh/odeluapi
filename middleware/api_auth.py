from fastapi import Request, HTTPException, Depends
from config import API_KEY

async def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Unauthorized: API Key missing"}
        )
    
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Unauthorized: Invalid API Key"}
        )
    
    return True