from fastapi import APIRouter, Depends, Query, Path, Request, Body, HTTPException
from typing import Optional, Dict, List

from controllers import report_controller
from models.report import ReportCreate, ReportUpdate, ReportReason
from middleware.auth_required import require_auth
from middleware.api_auth import verify_api_key
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# User endpoints
@router.post("/")
@limiter.limit("10/minute")
async def create_report(
    request: Request,
    report_data: ReportCreate,
    current_user = Depends(require_auth)
):
    """
    Create a new report for a movie or show
    """
    return await report_controller.create_report(report_data, current_user)

@router.get("/my-reports")
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_my_reports(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(require_auth)
):
    """
    Get reports submitted by the current user
    """
    user_id = current_user["_id"]
    return await report_controller.get_user_reports(user_id, page, limit)

@router.get("/reasons")
async def get_report_reasons():
    """
    Get the list of possible report reasons
    """
    return {
        "success": True,
        "data": {
            "reasons": [
                {"value": reason.value, "label": reason.name.lower().replace("_", " ")}
                for reason in ReportReason
            ]
        }
    } 