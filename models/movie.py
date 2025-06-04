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

class Movie(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    title: str
    description: str
    releaseYear: Optional[int] = None
    duration: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=10)
    tags: List[str] = []
    image: str
    coverImage: str
    hoverImage: Optional[str] = None
    links: List[Link] = []
    featured: bool = False
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "title": "Inception",
                "description": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
                "releaseYear": 2010,
                "duration": "2h 28min",
                "rating": 8.8,
                "tags": ["Action", "Adventure", "Sci-Fi"],
                "image": "https://example.com/inception.jpg",
                "coverImage": "https://example.com/inception-cover.jpg",
                "hoverImage": "https://example.com/inception-hover.jpg",
                "links": [
                    {"name": "Watch", "url": "https://example.com/watch/inception"}
                ],
                "featured": True
            }
        }
    )

class MovieInDB(Movie):
    id: PyObjectId = Field(alias="_id")