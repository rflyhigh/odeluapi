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

class Watchlist(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    userId: str
    contentType: str  # "movie" or "show"
    contentId: PyObjectId
    addedAt: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "userId": "user123",
                "contentType": "movie",
                "contentId": "60d21b4667d0d8992e610c85",
                "addedAt": "2023-11-01T12:00:00"
            }
        }
    )

class WatchlistInDB(Watchlist):
    id: PyObjectId = Field(alias="_id")