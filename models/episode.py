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

class Link(BaseModel):
    name: str
    url: str
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "name": "Watch",
                "url": "https://example.com/watch"
            }
        }
    )

class Episode(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    seasonId: PyObjectId
    episodeNumber: int = Field(..., ge=1)
    title: str
    description: str = ""
    image: str = ""
    duration: str = "0"
    links: List[Link] = []
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "seasonId": "60d21b4667d0d8992e610c85",
                "episodeNumber": 1,
                "title": "Chapter One: The Vanishing of Will Byers",
                "description": "On his way home from a friend's house, young Will sees something terrifying. Nearby, a sinister secret lurks in the depths of a government lab.",
                "image": "https://example.com/episode1.jpg",
                "duration": "47:00",
                "links": [
                    {"name": "Watch", "url": "https://example.com/watch/episode1"}
                ]
            }
        }
    )

class EpisodeInDB(Episode):
    id: PyObjectId = Field(alias="_id")