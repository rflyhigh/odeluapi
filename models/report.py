from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from enum import Enum

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)
        
    @classmethod
    def __get_pydantic_json_schema__(cls, _schema_generator):
        return {"type": "string"}

class ReportReason(str, Enum):
    PLAYING_SLOW = "playing_slow"
    NOT_PLAYING = "not_playing"
    WRONG_CONTENT = "wrong_content"
    AUDIO_ISSUES = "audio_issues"
    VIDEO_QUALITY = "video_quality"
    SUBTITLE_ISSUES = "subtitle_issues"
    OTHER = "other"

class ReportCreate(BaseModel):
    content_id: str
    content_type: str
    reason: ReportReason
    custom_message: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content_id": "6123456789abcdef01234567",
                "content_type": "movie",
                "reason": "not_playing",
                "custom_message": "Video stops after 10 minutes"
            }
        }
    )

class Report(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    content_id: PyObjectId
    content_type: str  # "movie" or "show"
    reason: ReportReason
    custom_message: Optional[str] = None
    user_id: Optional[PyObjectId] = None
    username: Optional[str] = None
    status: str = "pending"  # pending, resolved, rejected
    resolved_by: Optional[PyObjectId] = None
    resolution_message: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class ReportInDB(Report):
    pass

class ReportUpdate(BaseModel):
    status: str
    resolution_message: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "resolved",
                "resolution_message": "Fixed the playback issue"
            }
        }
    ) 