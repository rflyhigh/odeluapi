from typing import List, Optional, Any, Dict
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

class Season(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    showId: PyObjectId
    seasonNumber: int = Field(..., ge=1)
    title: str
    episodes: List[PyObjectId] = []
    releaseYear: Optional[int] = None
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "showId": "60d21b4667d0d8992e610c85",
                "seasonNumber": 1,
                "title": "Season 1",
                "episodes": [],
                "releaseYear": 2016
            }
        }
    )

class SeasonInDB(Season):
    id: PyObjectId = Field(alias="_id")