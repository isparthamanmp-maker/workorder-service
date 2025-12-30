# src/schemas/user.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Schema for API responses
class UserResponse(BaseModel):
    id: str = Field(alias="UserID")  # Map UserID to id
    name: Optional[str] = Field(None, alias="Name")
    user_group: Optional[str] = Field(None, alias="UserGroup")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True  # Allows using both alias and original name
    )

# Schema for creating users
class UserCreate(BaseModel):
    UserID: str = Field(..., min_length=1, max_length=50)
    Name: Optional[str] = Field(None, max_length=200)
    Password: Optional[str] = Field(None, max_length=50)
    UserGroup: Optional[str] = Field(None, max_length=50)

# Schema for updating users
class UserUpdate(BaseModel):
    Name: Optional[str] = Field(None, max_length=200)
    Password: Optional[str] = Field(None, max_length=50)
    UserGroup: Optional[str] = Field(None, max_length=50)