import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Date, SmallInteger, Numeric
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


class WorkOrders(Base):
    """work_orders model"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    document_number = Column(String(100), nullable=False)
    request_date = Column(Date, nullable=False)
    request_type = Column(String, nullable=False)
    submitted_by = Column(String, nullable=False)
    scope_of_works = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_urgent = Column(SmallInteger, nullable=True)
    budget_status = Column(String, nullable=True)
    cost_type = Column(String, nullable=True)
    budget_index = Column(String(50), nullable=True)
    budget_name = Column(String(200), nullable=True)
    cost_estimation = Column(Numeric(15,2), nullable=True)
    remaining_budget = Column(Numeric(15,2), nullable=True)
    under_over = Column(String(50), nullable=True)
    charge_to_tenant = Column(SmallInteger, nullable=True)
    recommended_contractor = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True)
    vendor_selection_method = Column(String, nullable=True)
    test_and_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<WorkOrders(id={id}, document_number='{document_number}', request_date={request_date})>"
    
