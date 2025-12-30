# src/repositories/work_orders_repository.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_
from src.models.base import WorkOrders

class WorkOrdersRepository:
    """work_orders repository with CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, work_orders_data: Dict[str, Any]) -> WorkOrders:
        """Create a new work_orders record"""
        work_orders = WorkOrders(**work_orders_data)
        self.db.add(work_orders)
        self.db.commit()
        self.db.refresh(work_orders)
        return work_orders

    def get_by_id(self, work_orders_id: int) -> Optional[WorkOrders]:
        """Get work_orders by id (primary key)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.id == work_orders_id,
        ).first()

    def get_by_document_number_like(self, document_number: str) -> List[WorkOrders]:
        """Get work_orderss by document_number (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.document_number.ilike(f"%{document_number}%"),
        ).all()

    def get_by_scope_of_works_like(self, scope_of_works: str) -> List[WorkOrders]:
        """Get work_orderss by scope_of_works (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.scope_of_works.ilike(f"%{scope_of_works}%"),
        ).all()

    def get_by_budget_index_like(self, budget_index: str) -> List[WorkOrders]:
        """Get work_orderss by budget_index (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.budget_index.ilike(f"%{budget_index}%"),
        ).all()

    def get_by_budget_name_like(self, budget_name: str) -> List[WorkOrders]:
        """Get work_orderss by budget_name (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.budget_name.ilike(f"%{budget_name}%"),
        ).all()

    def get_by_under_over_like(self, under_over: str) -> List[WorkOrders]:
        """Get work_orderss by under_over (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.under_over.ilike(f"%{under_over}%"),
        ).all()

    def get_by_recommended_contractor_like(self, recommended_contractor: str) -> List[WorkOrders]:
        """Get work_orderss by recommended_contractor (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.recommended_contractor.ilike(f"%{recommended_contractor}%"),
        ).all()

    def get_by_reason_like(self, reason: str) -> List[WorkOrders]:
        """Get work_orderss by reason (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.reason.ilike(f"%{reason}%"),
        ).all()

    def get_by_test_and_analysis_like(self, test_and_analysis: str) -> List[WorkOrders]:
        """Get work_orderss by test_and_analysis (partial match)"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.test_and_analysis.ilike(f"%{test_and_analysis}%"),
        ).all()

    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "id",
        order_desc: bool = False
    ) -> List[WorkOrders]:
        """Get all work_orderss with optional filtering and ordering"""
        query = self.db.query(WorkOrders)
        
        if filters:
            for key, value in filters.items():
                if hasattr(WorkOrders, key):
                    # Handle None values for nullable fields
                    if value is None:
                        query = query.filter(getattr(WorkOrders, key).is_(None))
                    else:
                        query = query.filter(getattr(WorkOrders, key) == value)
        
        # Apply ordering
        if hasattr(WorkOrders, order_by):
            order_column = getattr(WorkOrders, order_by)
            if order_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        else:
            # Fallback to default ordering by primary key
            if order_desc:
                query = query.order_by(desc(WorkOrders.id))
            else:
                query = query.order_by(asc(WorkOrders.id))
        
        return query.offset(skip).limit(limit).all()

    def update(self, work_orders_id: int, work_orders_data: Dict[str, Any]) -> Optional[WorkOrders]:
        """Update work_orders"""
        work_orders = self.get_by_id(work_orders_id)
        if not work_orders:
            return None
        
        # Only update allowed fields (exclude id)
        allowed_fields = [
            'document_number',
            'request_date',
            'request_type',
            'submitted_by',
            'scope_of_works',
            'start_date',
            'end_date',
            'is_urgent',
            'budget_status',
            'cost_type',
            'budget_index',
            'budget_name',
            'cost_estimation',
            'remaining_budget',
            'under_over',
            'charge_to_tenant',
            'recommended_contractor',
            'reason',
            'vendor_selection_method',
            'test_and_analysis',
            'created_at',
            'updated_at',
        ]
        
        for key, value in work_orders_data.items():
            if hasattr(work_orders, key) and key in allowed_fields:
                setattr(work_orders, key, value)
        
        self.db.commit()
        self.db.refresh(work_orders)
        return work_orders

    def delete(self, work_orders_id: int) -> bool:
        """Delete work_orders (hard delete since no soft delete field)"""
        work_orders = self.get_by_id(work_orders_id)
        if not work_orders:
            return False
        
        self.db.delete(work_orders)
        self.db.commit()
        return True

    def search(
        self, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 100,
        order_by: str = "id",
        order_desc: bool = False
    ) -> List[WorkOrders]:
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
        else:
            # If no search term, return all
            pass
        
        # Apply ordering
        if hasattr(WorkOrders, order_by):
            order_column = getattr(WorkOrders, order_by)
            if order_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        else:
            if order_desc:
                query = query.order_by(desc(WorkOrders.id))
            else:
                query = query.order_by(asc(WorkOrders.id))
        
        return query.offset(skip).limit(limit).all()

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count work_orderss with optional filters"""
        query = self.db.query(WorkOrders)
        
        if filters:
            for key, value in filters.items():
                if hasattr(WorkOrders, key):
                    if value is None:
                        query = query.filter(getattr(WorkOrders, key).is_(None))
                    else:
                        query = query.filter(getattr(WorkOrders, key) == value)
        
        return query.count()

    def exists(self, work_orders_id: int) -> bool:
        """Check if work_orders exists"""
        return self.db.query(WorkOrders).filter(
            WorkOrders.id == work_orders_id
        ).first() is not None

    def get_document_number_values(self) -> List[str]:
        """Get list of all unique document_number values"""
        results = self.db.query(WorkOrders.document_number).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_scope_of_works_values(self) -> List[str]:
        """Get list of all unique scope_of_works values"""
        results = self.db.query(WorkOrders.scope_of_works).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_budget_index_values(self) -> List[str]:
        """Get list of all unique budget_index values"""
        results = self.db.query(WorkOrders.budget_index).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_budget_name_values(self) -> List[str]:
        """Get list of all unique budget_name values"""
        results = self.db.query(WorkOrders.budget_name).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_under_over_values(self) -> List[str]:
        """Get list of all unique under_over values"""
        results = self.db.query(WorkOrders.under_over).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_recommended_contractor_values(self) -> List[str]:
        """Get list of all unique recommended_contractor values"""
        results = self.db.query(WorkOrders.recommended_contractor).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_reason_values(self) -> List[str]:
        """Get list of all unique reason values"""
        results = self.db.query(WorkOrders.reason).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_test_and_analysis_values(self) -> List[str]:
        """Get list of all unique test_and_analysis values"""
        results = self.db.query(WorkOrders.test_and_analysis).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def bulk_create(self, work_orders_data_list: List[Dict[str, Any]]) -> List[WorkOrders]:
        """Create multiple work_orders records"""
        work_orderss = [WorkOrders(**data) for data in work_orders_data_list]
        self.db.add_all(work_orderss)
        self.db.commit()
        for work_orders in work_orderss:
            self.db.refresh(work_orders)
        return work_orderss

    def bulk_delete(self, work_orders_ids: List[int]) -> int:
        """Delete multiple work_orderss by IDs"""
        deleted_count = self.db.query(WorkOrders)\
            .filter(WorkOrders.id.in_(work_orders_ids))\
            .delete(synchronize_session=False)
        self.db.commit()
        return deleted_count