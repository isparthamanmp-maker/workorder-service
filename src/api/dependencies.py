from fastapi import Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.services.user_service import UserService

# Use Depends properly
def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Get user service dependency"""
    return UserService(db)