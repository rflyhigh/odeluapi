from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, EmailStr
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

class UserBase(BaseModel):
    username: str
    email: EmailStr
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar: str = "default.png"  # Default avatar
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

class User(UserBase):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    watchlist: List[Dict[str, str]] = []  # List of {id: string, type: "movie"|"show"}
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)

class UserInDB(User):
    id: PyObjectId = Field(alias="_id")
    hashed_password: str