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

class Show(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    title: str
    description: str
    startYear: Optional[int] = None
    endYear: Optional[int] = None
    status: str = "Ongoing"
    rating: Optional[float] = Field(None, ge=0, le=10)
    tags: List[str] = []
    image: str
    coverImage: str
    hoverImage: Optional[str] = None
    featured: bool = False
    seasons: List[PyObjectId] = []
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "title": "Stranger Things",
                "description": "When a young boy disappears, his mother, a police chief, and his friends must confront terrifying supernatural forces in order to get him back.",
                "startYear": 2016,
                "endYear": None,
                "status": "Ongoing",
                "rating": 8.7,
                "tags": ["Drama", "Fantasy", "Horror"],
                "image": "https://example.com/stranger-things.jpg",
                "coverImage": "https://example.com/stranger-things-cover.jpg",
                "hoverImage": "https://example.com/stranger-things-hover.jpg",
                "featured": True,
                "seasons": []
            }
        }
    )

class ShowInDB(Show):
    id: PyObjectId = Field(alias="_id")