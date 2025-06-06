from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

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

class Comment(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    content: str
    user_id: PyObjectId
    username: str
    avatar: Optional[str] = None
    content_id: PyObjectId  # ID of the movie or show
    content_type: str  # "movie" or "show"
    parent_id: Optional[PyObjectId] = None  # ID of parent comment if this is a reply
    replies: Optional[List[PyObjectId]] = []  # List of reply comment IDs
    nesting_level: int = 1  # Nesting level (1 for top-level comments, increases with depth)
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class CommentCreate(BaseModel):
    content: str
    content_id: str
    content_type: str
    parent_id: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "This is an amazing movie!",
                "content_id": "6123456789abcdef01234567",
                "content_type": "movie",
                "parent_id": None  # Optional parent comment ID for replies
            }
        }
    )

class CommentInDB(Comment):
    pass 