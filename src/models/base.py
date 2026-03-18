# src/models/base.py
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, SmallInteger, Numeric, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Authorizations(Base):
    """authorizations model"""
    __tablename__ = "authorizations"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'), nullable=False)
    authorization_type = Column(String(50), nullable=False)
    person_name = Column(String(200), nullable=True)
    authorization_date = Column(Date, nullable=True)
    
    # Use string reference for relationship
    work_order = relationship("WorkOrders", back_populates="authorizations")
    
    def __repr__(self):
        return f"<Authorizations(id={self.id}, type='{self.authorization_type}', person='{self.person_name}')>"


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


class SupportingDocuments(Base):
    """supporting_documents model"""
    __tablename__ = "supporting_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'), nullable=False)
    document_type = Column(String(100), nullable=False)
    has_document = Column(Boolean, default=False)
    
    # Use string reference for relationship
    work_order = relationship("WorkOrders", back_populates="supporting_documents")
    
    def __repr__(self):
        return f"<SupportingDocuments(id={self.id}, document_type='{self.document_type}', has_document={self.has_document})>"


class WorkOrders(Base):
    """work_orders model"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    document_number = Column(String(100), nullable=False, unique=True)
    request_date = Column(Date, nullable=False)
    request_type = Column(String(100), nullable=False)
    submitted_by = Column(String(100), nullable=False)
    scope_of_works = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_urgent = Column(SmallInteger, nullable=True, default=0)
    budget_status = Column(String(50), nullable=True)
    cost_type = Column(String(50), nullable=True)
    budget_index = Column(String(50), nullable=True)
    budget_name = Column(String(200), nullable=True)
    cost_estimation = Column(Numeric(15,2), nullable=True)
    remaining_budget = Column(Numeric(15,2), nullable=True)
    under_over = Column(String(50), nullable=True)
    charge_to_tenant = Column(SmallInteger, nullable=True, default=0)
    recommended_contractor = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True)
    vendor_selection_method = Column(String(100), nullable=True)
    test_and_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
    status = Column(String(100), nullable=False, default='Draft')
    
    # Use string references for relationships
    work_items = relationship("WorkOrderItems", back_populates="work_order", cascade="all, delete-orphan")
    vendors = relationship("WorkOrderVendors", back_populates="work_order", cascade="all, delete-orphan")
    supporting_documents = relationship("SupportingDocuments", back_populates="work_order", cascade="all, delete-orphan")
    authorizations = relationship("Authorizations", back_populates="work_order", cascade="all, delete-orphan")
    budget_entries = relationship(
        "WorkOrderBudgets",
        back_populates="work_order",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


    def __repr__(self):
        return f"<WorkOrders(id={self.id}, document_number='{self.document_number}')>"
        


class WorkOrderFiles(Base):
    """work_order_files model to store file information"""
    __tablename__ = "work_order_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'), nullable=False)
    supporting_document_id = Column(Integer, ForeignKey('supporting_documents.id'), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)  # MinIO URL
    file_size = Column(Integer, nullable=True)  # Size in bytes
    upload_date = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    
    # Relationships - using string references to avoid circular imports
    work_order = relationship("WorkOrders", back_populates="files")
    supporting_document = relationship("SupportingDocuments", back_populates="files")
    
    def __repr__(self):
        return f"<WorkOrderFiles(id={self.id}, file_name='{self.file_name}')>"


# Add relationships after all classes are defined
# This needs to be done after class definitions to avoid circular references
SupportingDocuments.files = relationship("WorkOrderFiles", back_populates="supporting_document", cascade="all, delete-orphan")
WorkOrders.files = relationship("WorkOrderFiles", back_populates="work_order", cascade="all, delete-orphan")


class WorkOrdersHistory(Base):
    """work_orders_history model"""
    __tablename__ = "work_orders_history"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    UserGroup = Column(String(100), nullable=False)
    authorization_type = Column(String(100), nullable=False)
    status = Column(String(100), nullable=False)
    refid = Column(Integer, nullable=False)
    refnum = Column(String(100), nullable=False)
    refvalue = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    created_by = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)

    def __repr__(self):
        return f"<WorkOrdersHistory(id={self.id}, refnum='{self.refnum}', status='{self.status}')>"
    
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

class WorkOrderBudgets(Base):
    """budgets model"""
    __tablename__ = "work_order_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)  # Add ForeignKey
    budget_index = Column(String(50), nullable=False, unique=True)
    budget_name = Column(String(255), nullable=False)
    cost_estimation = Column(BigInteger, nullable=False)
    budget_remaining = Column(BigInteger, nullable=False)
    under_over = Column(Numeric(15, 2), nullable=False)
    entry_order = Column(Integer, nullable=False)
    is_selected = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    work_order = relationship("WorkOrders", back_populates="budget_entries")

    def __repr__(self):
        return (
            f"<Budgets(id={self.id}, "
            f"budget_index='{self.budget_index}', "
            f"budget_name='{self.budget_name}')>"
        )
        