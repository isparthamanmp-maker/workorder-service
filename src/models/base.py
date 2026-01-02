# src/models/base.py
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, SmallInteger, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Define WorkOrderItems FIRST, using string reference for relationship
class WorkOrderItems(Base):
    """work_order_items model"""
    __tablename__ = "work_order_items"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'), nullable=False)
    description = Column(Text, nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False, default=1.00)
    unit_price = Column(Numeric(15, 2), nullable=False, default=0.00)
    total_price = Column(Numeric(15, 2), nullable=False, default=0.00)
    item_order = Column(Integer, nullable=True, default=0)
    
    # Use string reference for relationship
    work_order = relationship("WorkOrders", back_populates="work_items")
    
    def __repr__(self):
        return f"<WorkOrderItems(id={self.id}, description='{self.description[:50]}...')>"


# Define WorkOrderVendors SECOND, also using string reference
class WorkOrderVendors(Base):
    """work_order_vendors model"""
    __tablename__ = "work_order_vendors"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'), nullable=False)
    vendor_name = Column(String(200), nullable=True)
    
    # Use string reference for relationship
    work_order = relationship("WorkOrders", back_populates="vendors")
    
    def __repr__(self):
        return f"<WorkOrderVendors(id={self.id}, vendor_name='{self.vendor_name}')>"


# Define WorkOrders LAST, now it can reference the already-defined classes
class WorkOrders(Base):
    """work_orders model"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    document_number = Column(String(100), nullable=False, unique=True)
    request_date = Column(Date, nullable=False)
    request_type = Column(String, nullable=False)
    submitted_by = Column(String, nullable=False)
    scope_of_works = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_urgent = Column(SmallInteger, nullable=True, default=0)
    budget_status = Column(String, nullable=True)
    cost_type = Column(String, nullable=True)
    budget_index = Column(String(50), nullable=True)
    budget_name = Column(String(200), nullable=True)
    cost_estimation = Column(Numeric(15,2), nullable=True)
    remaining_budget = Column(Numeric(15,2), nullable=True)
    under_over = Column(String(50), nullable=True)
    charge_to_tenant = Column(SmallInteger, nullable=True, default=0)
    recommended_contractor = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True)
    vendor_selection_method = Column(String, nullable=True)
    test_and_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True, server_default='CURRENT_TIMESTAMP')
    updated_at = Column(DateTime, nullable=True, onupdate='CURRENT_TIMESTAMP')
    
    # Now we can reference the already-defined classes
    work_items = relationship("WorkOrderItems", back_populates="work_order", cascade="all, delete-orphan")
    vendors = relationship("WorkOrderVendors", back_populates="work_order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkOrders(id={self.id}, document_number='{self.document_number}')>"


# If you have User model, define it AFTER WorkOrders if they have relationships
class User(Base):
    """user model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    # ... other columns ...
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"