import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from src.config.database import Base
from sqlalchemy.ext.declarative import declarative_base

# Create base from declarative_base
Base = declarative_base()

class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True
    
    # id = Column(Integer, primary_key=True, index=True)
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # is_active = Column(Boolean, default=True)

class User(BaseModel):
    """User model"""
    __tablename__ = "usertable" 

    # Conditionally add schema
    if os.getenv("DB_ENGINE", "").lower() == "sqlserver":
        __tablename__ = "UserTable"
        __table_args__ = {'schema': 'dbo'}
    
    Name = Column(String(200), nullable=True)
    UserID = Column(String(50), nullable=True, primary_key=True)
    Password = Column(String(50), nullable=True)
    UserGroup = Column(String(50), nullable=True)
    
