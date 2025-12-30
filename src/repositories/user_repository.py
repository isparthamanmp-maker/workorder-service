from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_
from src.models.base import User

class UserRepository:
    """User repository with CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_data: Dict[str, Any]) -> User:
        """Create a new user"""
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_by_UserID(self, UserID: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(
            User.id == UserID,
        ).first()
    
    
    def get_by_Name(self, Name: str) -> Optional[User]:
        """Get user by Name"""
        return self.db.query(User).filter(
            User.Name == Name,
        ).first()
    
    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "id"  # Add order_by parameter
    ) -> List[User]:
        """Get all users with optional filtering and ordering"""
        query = self.db.query(User)
        
        if filters:
            for key, value in filters.items():
                if hasattr(User, key):
                    query = query.filter(getattr(User, key) == value)
        
        # SQL Server requires ORDER BY for OFFSET/LIMIT
        # Default to ordering by id
        if hasattr(User, order_by):
            query = query.order_by(getattr(User, order_by))
        else:
            query = query.order_by(User.UserID)  # Fallback to id
        
        return query.offset(skip).limit(limit).all()
    
    def update(self, user_id: int, user_data: Dict[str, Any]) -> Optional[User]:
        """Update user"""
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def delete(self, user_id: int) -> bool:
        """Soft delete user"""
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        self.db.commit()
        return True
    
    def hard_delete(self, user_id: int) -> bool:
        """Hard delete user"""
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        self.db.delete(user)
        self.db.commit()
        return True
    
    def search(self, search_term: str, skip: int = 0, limit: int = 100) -> List[User]:
        """Search users by username, email, or full name"""
        return self.db.query(User).filter(
            (
                User.username.ilike(f"%{search_term}%"),
                User.full_name.ilike(f"%{search_term}%")
            )
        ).offset(skip).limit(limit).all()