from fastapi import HTTPException, status
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo import DESCENDING
import logging
from datetime import datetime

from database import report_collection, movie_collection, show_collection, serialize_doc
from models.report import ReportCreate, Report, ReportUpdate, ReportReason

logger = logging.getLogger(__name__)

async def create_report(report_data: ReportCreate, current_user=None):
    """
    Create a new report for a movie or show
    """
    try:
        # Validate content type
        if report_data.content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
            
        # Validate content exists
        content_id = ObjectId(report_data.content_id)
        if report_data.content_type == "movie":
            content = await movie_collection.find_one({"_id": content_id}, projection={"_id": 1, "title": 1})
        else:
            content = await show_collection.find_one({"_id": content_id}, projection={"_id": 1, "title": 1})
            
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": f"{report_data.content_type.capitalize()} not found"}
            )
        
        # Create report document
        now = datetime.now()
        report_dict = {
            "content_id": content_id,
            "content_type": report_data.content_type,
            "reason": report_data.reason,
            "custom_message": report_data.custom_message,
            "status": "pending",
            "createdAt": now,
            "updatedAt": now,
            "content_title": content.get("title", "Unknown Title")
        }
        
        # Add user info if authenticated
        if current_user:
            report_dict["user_id"] = ObjectId(current_user["_id"])
            report_dict["username"] = current_user["username"]
        
        # Insert report
        result = await report_collection.insert_one(report_dict)
        
        # Get created report
        created_report = await report_collection.find_one({"_id": result.inserted_id})
        
        return {"success": True, "data": serialize_doc(created_report)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_all_reports(page: int = 1, limit: int = 20, status: Optional[str] = None, content_type: Optional[str] = None):
    """
    Get all reports with pagination and optional filtering
    Admin only endpoint
    """
    try:
        skip = (page - 1) * limit
        
        # Build query
        query = {}
        if status:
            query["status"] = status
        if content_type:
            query["content_type"] = content_type
        
        # Get reports
        cursor = report_collection.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        reports = await cursor.to_list(length=limit)
        
        # Get total count
        total = await report_collection.count_documents(query)
        
        return {
            "success": True,
            "data": {
                "reports": serialize_doc(reports),
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except Exception as e:
        logger.error(f"Error in get_all_reports: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_report_by_id(report_id: str):
    """
    Get a specific report by ID
    Admin only endpoint
    """
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(report_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid report ID format"}
            )
        
        # Get report
        report = await report_collection.find_one({"_id": ObjectId(report_id)})
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Report not found"}
            )
        
        return {"success": True, "data": serialize_doc(report)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_report_by_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def update_report_status(report_id: str, update_data: ReportUpdate, admin_user):
    """
    Update a report's status
    Admin only endpoint
    """
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(report_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid report ID format"}
            )
        
        # Validate status
        valid_statuses = ["pending", "resolved", "rejected"]
        if update_data.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            )
        
        # Get report
        report = await report_collection.find_one({"_id": ObjectId(report_id)})
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Report not found"}
            )
        
        # Update report
        update_dict = {
            "status": update_data.status,
            "updatedAt": datetime.now(),
            "resolved_by": ObjectId(admin_user["_id"])
        }
        
        if update_data.resolution_message:
            update_dict["resolution_message"] = update_data.resolution_message
        
        await report_collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": update_dict}
        )
        
        # Get updated report
        updated_report = await report_collection.find_one({"_id": ObjectId(report_id)})
        
        return {"success": True, "data": serialize_doc(updated_report)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_report_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_report_counts():
    """
    Get counts of reports by status and type
    Admin only endpoint
    """
    try:
        # Get counts by status
        status_pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        status_cursor = report_collection.aggregate(status_pipeline)
        status_counts = await status_cursor.to_list(length=None)
        
        # Get counts by content type
        type_pipeline = [
            {"$group": {"_id": "$content_type", "count": {"$sum": 1}}}
        ]
        type_cursor = report_collection.aggregate(type_pipeline)
        type_counts = await type_cursor.to_list(length=None)
        
        # Get counts by reason
        reason_pipeline = [
            {"$group": {"_id": "$reason", "count": {"$sum": 1}}}
        ]
        reason_cursor = report_collection.aggregate(reason_pipeline)
        reason_counts = await reason_cursor.to_list(length=None)
        
        # Format results
        status_dict = {item["_id"]: item["count"] for item in status_counts}
        type_dict = {item["_id"]: item["count"] for item in type_counts}
        reason_dict = {item["_id"]: item["count"] for item in reason_counts}
        
        # Get total count
        total = await report_collection.count_documents({})
        
        return {
            "success": True,
            "data": {
                "total": total,
                "by_status": status_dict,
                "by_type": type_dict,
                "by_reason": reason_dict
            }
        }
    except Exception as e:
        logger.error(f"Error in get_report_counts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def delete_report(report_id: str):
    """
    Delete a report
    Admin only endpoint
    """
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(report_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid report ID format"}
            )
        
        # Delete report
        result = await report_collection.delete_one({"_id": ObjectId(report_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"success": False, "message": "Report not found"}
            )
        
        return {"success": True, "message": "Report deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_user_reports(user_id: str, page: int = 1, limit: int = 20):
    """
    Get reports submitted by a specific user
    """
    try:
        skip = (page - 1) * limit
        
        # Build query
        query = {"user_id": ObjectId(user_id)}
        
        # Get reports
        cursor = report_collection.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        reports = await cursor.to_list(length=limit)
        
        # Get total count
        total = await report_collection.count_documents(query)
        
        return {
            "success": True,
            "data": {
                "reports": serialize_doc(reports),
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit  # Ceiling division
            }
        }
    except Exception as e:
        logger.error(f"Error in get_user_reports: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        )

async def get_content_reports(content_id: str, content_type: str, page: int = 1, limit: int = 20):
    """
    Get reports for a specific content item (movie or show)
    Admin only endpoint
    """
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(content_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content ID format"}
            )
        
        # Validate content type
        if content_type not in ["movie", "show"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Invalid content type. Must be 'movie' or 'show'"}
            )
        
        skip = (page - 1) * limit
        
        # Build query
        query = {
            "content_id": ObjectId(content_id),
            "content_type": content_type
        }
        
        # Get reports
        cursor = report_collection.find(query).sort("createdAt", DESCENDING).skip(skip).limit(limit)
        reports = await cursor.to_list(length=limit)
        
        # Get total count
        total = await report_collection.count_documents(query)
        
        # Get content title
        if content_type == "movie":
            content = await movie_collection.find_one({"_id": ObjectId(content_id)}, projection={"title": 1})
        else:
            content = await show_collection.find_one({"_id": ObjectId(content_id)}, projection={"title": 1})
        
        content_title = content.get("title", "Unknown Title") if content else "Unknown Title"
        
        return {
            "success": True,
            "data": {
                "reports": serialize_doc(reports),
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit,  # Ceiling division
                "content": {
                    "id": content_id,
                    "type": content_type,
                    "title": content_title
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_content_reports: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": str(e)}
        ) 