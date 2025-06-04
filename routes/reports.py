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

# Admin endpoints
@router.get("/admin", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_all_reports(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, resolved, rejected"),
    content_type: Optional[str] = Query(None, description="Filter by content type: movie, show"),
    current_user = Depends(require_auth)
):
    """
    Get all reports with pagination and optional filtering (Admin only)
    """
    return await report_controller.get_all_reports(page, limit, status, content_type)

@router.get("/admin/counts", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_report_counts(
    request: Request,
    current_user = Depends(require_auth)
):
    """
    Get counts of reports by status and type (Admin only)
    """
    return await report_controller.get_report_counts()

@router.get("/admin/{report_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_report_by_id(
    request: Request,
    report_id: str = Path(..., description="The ID of the report to get"),
    current_user = Depends(require_auth)
):
    """
    Get a specific report by ID (Admin only)
    """
    return await report_controller.get_report_by_id(report_id)

@router.put("/admin/{report_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def update_report_status(
    request: Request,
    report_id: str = Path(..., description="The ID of the report to update"),
    update_data: ReportUpdate = Body(...),
    current_user = Depends(require_auth)
):
    """
    Update a report's status (Admin only)
    """
    return await report_controller.update_report_status(report_id, update_data, current_user)

@router.delete("/admin/{report_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def delete_report(
    request: Request,
    report_id: str = Path(..., description="The ID of the report to delete"),
    current_user = Depends(require_auth)
):
    """
    Delete a report (Admin only)
    """
    return await report_controller.delete_report(report_id)

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

@router.get("/admin/content/{content_type}/{content_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT_DEFAULT)
async def get_content_reports(
    request: Request,
    content_type: str = Path(..., description="Type of content: movie or show"),
    content_id: str = Path(..., description="ID of the content to get reports for"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(require_auth)
):
    """
    Get reports for a specific content item (Admin only)
    """
    return await report_controller.get_content_reports(content_id, content_type, page, limit)

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