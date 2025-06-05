from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, EmailStr, validator
from bson import ObjectId
import re
import pytz

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
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar: str = "default.jpeg"  # Default avatar
    timezone: str = "Asia/Kolkata"  # Default timezone (Indian)
    
    @validator('username')
    def validate_username(cls, v):
        # Only allow alphanumeric characters, underscores, and hyphens
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError("Username can only contain letters, numbers, underscores and hyphens")
        
        # Prevent NoSQL injection and XSS attacks
        if re.search(r'^\$|\.|\{|\}|;|javascript:|<script|<\/script>|<|>|\"|\\\|\/\*|\*\/', v, re.IGNORECASE):
            raise ValueError("Username contains invalid characters")
        
        return v
    
    @validator('timezone')
    def validate_timezone(cls, v):
        # Validate timezone is a valid pytz timezone
        if v not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {v}")
        return v
    
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
    timezone: Optional[str] = None
    
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