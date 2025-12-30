# src/services/work_orders_service.py
from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.base import WorkOrders
from src.schemas.work_orders_schema import WorkOrdersCreate, WorkOrdersUpdate

class WorkOrdersService:
    """work_orders service layer using Pydantic schemas"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_work_orders(self, work_orders_data: WorkOrdersCreate) -> WorkOrders:
        """Create a new work_orders record from Pydantic schema"""
        # Convert schema to dict (handles aliases)
        work_orders_dict = work_orders_data.model_dump(by_alias=True)
        
        # Create new work_orders
        work_orders = WorkOrders(**work_orders_dict)
        
        self.db.add(work_orders)
        self.db.commit()
        self.db.refresh(work_orders)
        return work_orders
    
    def get_work_orders(self, work_orders_id: int) -> Optional[WorkOrders]:
        """Get work_orders by ID"""
        return self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
    
    def get_work_orderss(self, skip: int = 0, limit: int = 100, order_by: str = "id") -> List[WorkOrders]:
        """Get work_orderss with pagination and ordering"""
        # Map the alias to actual column names
        order_column_map = {
            "id": WorkOrders.id,
            "document_number": WorkOrders.document_number,
            "request_date": WorkOrders.request_date,
            "request_type": WorkOrders.request_type,
            "submitted_by": WorkOrders.submitted_by,
            "scope_of_works": WorkOrders.scope_of_works,
            "start_date": WorkOrders.start_date,
            "end_date": WorkOrders.end_date,
            "is_urgent": WorkOrders.is_urgent,
            "budget_status": WorkOrders.budget_status,
            "cost_type": WorkOrders.cost_type,
            "budget_index": WorkOrders.budget_index,
            "budget_name": WorkOrders.budget_name,
            "cost_estimation": WorkOrders.cost_estimation,
            "remaining_budget": WorkOrders.remaining_budget,
            "under_over": WorkOrders.under_over,
            "charge_to_tenant": WorkOrders.charge_to_tenant,
            "recommended_contractor": WorkOrders.recommended_contractor,
            "reason": WorkOrders.reason,
            "vendor_selection_method": WorkOrders.vendor_selection_method,
            "test_and_analysis": WorkOrders.test_and_analysis,
            "created_at": WorkOrders.created_at,
            "updated_at": WorkOrders.updated_at,
        }
        
        # Get the column to order by (default to id)
        order_column = order_column_map.get(order_by, WorkOrders.id)
        
        return self.db.query(WorkOrders)\
            .order_by(order_column)\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    def update_work_orders(self, work_orders_id: int, work_orders_data: WorkOrdersUpdate) -> Optional[WorkOrders]:
        """Update work_orders record from Pydantic schema"""
        work_orders = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        if not work_orders:
            return None
        
        # Convert schema to dict (exclude unset fields)
        update_dict = work_orders_data.model_dump(exclude_unset=True, by_alias=True)
        
        # Update fields
        for key, value in update_dict.items():
            if hasattr(work_orders, key):
                setattr(work_orders, key, value)
        
        self.db.commit()
        self.db.refresh(work_orders)
        return work_orders
    
    def delete_work_orders(self, work_orders_id: int) -> bool:
        """Delete work_orders record"""
        work_orders = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        if not work_orders:
            return False
        
        self.db.delete(work_orders)
        self.db.commit()
        return True
    
    def search_work_orderss(self, search_term: str, skip: int = 0, limit: int = 100) -> List[WorkOrders]:
        """Search work_orderss by search term"""
        query = self.db.query(WorkOrders)
        
        if search_term:
            # Create OR conditions for all searchable columns
            from sqlalchemy import or_
            conditions = []
            conditions.append(WorkOrders.document_number.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.scope_of_works.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.budget_index.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.budget_name.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.under_over.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.recommended_contractor.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.reason.ilike(f"%{search_term}%"))
            conditions.append(WorkOrders.test_and_analysis.ilike(f"%{search_term}%"))
            
            if conditions:
                query = query.filter(or_(*conditions))
        
        return query.order_by(WorkOrders.id).offset(skip).limit(limit).all()
    
    def count_work_orderss(self) -> int:
        """Count total work_orders records"""
        return self.db.query(WorkOrders).count()