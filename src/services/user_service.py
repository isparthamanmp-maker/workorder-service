from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.base import User

class UserService:
    """User service layer"""
    
    def __init__(self, db: Session):
        self.db = db  # Store the database session directly
    
    def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create a new user with validation"""
        # Check if UserID already exists
        if self.db.query(User).filter(User.UserID == user_data.get("UserID")).first():
            raise ValueError("UserID already taken")
        
        # Create new user
        user = User(
            UserID=user_data.get("UserID"),
            Name=user_data.get("Name"),
            Password=user_data.get("Password"),
            UserGroup=user_data.get("UserGroup")
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:  # Changed to string
        """Get user by UserID (string)"""
        return self.db.query(User).filter(User.UserID == user_id).first()
    
    def get_users(self, skip: int = 0, limit: int = 100, order_by: str = "UserID") -> List[User]:
        """Get users with pagination"""
        query = self.db.query(User)
        
        # Apply ordering
        if hasattr(User, order_by):
            query = query.order_by(getattr(User, order_by))
        else:
            query = query.order_by(User.UserID)
        
        return query.offset(skip).limit(limit).all()
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[User]:  # Changed to string
        """Update user with validation"""
        user = self.db.query(User).filter(User.UserID == user_id).first()
        if not user:
            return None
        
        # Update fields
        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def delete_user(self, user_id: str) -> bool:  # Changed to string
        """Delete user"""
        user = self.db.query(User).filter(User.UserID == user_id).first()
        if not user:
            return False
        
        self.db.delete(user)
        self.db.commit()
        return True
    
    def search_users(self, search_term: str, skip: int = 0, limit: int = 100) -> List[User]:
        """Search users by Name or UserID"""
        query = self.db.query(User)
        
        # Search in Name or UserID fields
        query = query.filter(
            (User.Name.ilike(f"%{search_term}%")) | 
            (User.UserID.ilike(f"%{search_term}%"))
        )
        
        return query.offset(skip).limit(limit).all()
    
    def authenticate_user(self, UserID: str, password: str) -> Optional[User]:
        """Authenticate user"""
        user = self.db.query(User).filter(User.UserID == UserID).first()
        if user and user.Password == password:  # Note: your field is Password, not hashed_password
            return user
        return None