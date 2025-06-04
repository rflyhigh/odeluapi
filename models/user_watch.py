from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
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

class UserWatch(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    userId: str  # User ID from authentication or cookie
    contentType: str
    contentId: PyObjectId
    watchedAt: datetime = Field(default_factory=datetime.now)
    progress: float = Field(0, ge=0, le=100)
    completed: bool = False
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "userId": "user123",
                "contentType": "movie",
                "contentId": "60d21b4667d0d8992e610c85",
                "watchedAt": "2023-11-01T12:00:00",
                "progress": 45.5,
                "completed": False
            }
        }
    )

class UserWatchInDB(UserWatch):
    id: PyObjectId = Field(alias="_id")