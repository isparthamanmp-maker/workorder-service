from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

from src.config.database import get_db
from src.services.user_service import UserService
from src.api.dependencies import get_user_service

# Pydantic schemas
class UserBase(BaseModel):
    UserID: str = Field(..., description="User identifier")
    Name: Optional[str] = Field(None, description="Full name")
    UserGroup: Optional[str] = Field(None, description="User group/role")

class UserCreate(BaseModel):
    UserID: str = Field(..., min_length=1, max_length=50)
    Name: Optional[str] = Field(None, max_length=200)
    Password: Optional[str] = Field(None, max_length=50)
    UserGroup: Optional[str] = Field(None, max_length=50)

class UserUpdate(BaseModel):
    Name: Optional[str] = Field(None, max_length=200)
    Password: Optional[str] = Field(None, max_length=50)
    UserGroup: Optional[str] = Field(None, max_length=50)

class UserResponse(BaseModel):
    UserID: str
    Name: Optional[str] = None
    UserGroup: Optional[str] = None
    
    class Config:
        from_attributes = True  # Allows SQLAlchemy -> Pydantic conversion

# Router
router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    """Create a new user"""
    try:
        # Convert Pydantic model to dict for service
        user_data = user.dict()
        created_user = user_service.create_user(user_data)
        return created_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    order_by: str = Query("UserID", description="Field to order by (UserID, Name, UserGroup)"),
    search: Optional[str] = None,
    user_service: UserService = Depends(get_user_service)
):
    """Get all users with pagination and search"""
    if search:
        return user_service.search_users(search, skip, limit)
    
    # Validate order_by field
    valid_order_fields = ["UserID", "Name", "UserGroup"]
    if order_by not in valid_order_fields:
        order_by = "UserID"  # Default to UserID if invalid
    
    return user_service.get_users(skip, limit, order_by=order_by)

@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    user_service: UserService = Depends(get_user_service)
):
    """Get all users with pagination and search"""
    if search:
        return user_service.search_users(search, skip, limit)
    return user_service.get_users(skip, limit)

@router.get("/{user_id}", response_model=UserResponse)  # Single UserResponse, not List
def get_user(
    user_id: str,  # Add user_id parameter
    user_service: UserService = Depends(get_user_service)
):
    """Get a single user by UserID"""
    user = user_service.get_user(user_id)  # Use get_user (singular) method
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,  # Changed from int to string (UserID is string)
    user_update: UserUpdate,
    user_service: UserService = Depends(get_user_service)
):
    """Update user"""
    try:
        updated_user = user_service.update_user(user_id, user_update.dict(exclude_unset=True))
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        return updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,  # Changed from int to string
    user_service: UserService = Depends(get_user_service)
):
    """Delete user"""
    if not user_service.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")

@router.post("/authenticate")
def authenticate(
    UserID: str,
    password: str,
    user_service: UserService = Depends(get_user_service)
):
    """Authenticate user"""
    user = user_service.authenticate_user(UserID, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Authentication successful", "user_id": user.UserID}  # Changed to user.UserID