# src/repositories/work_orders_history_repository.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_
from src.models.base import WorkOrdersHistory

class WorkOrdersHistoryRepository:
    """work_orders_history repository with CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, work_orders_history_data: Dict[str, Any]) -> WorkOrdersHistory:
        """Create a new work_orders_history record"""
        work_orders_history = WorkOrdersHistory(**work_orders_history_data)
        self.db.add(work_orders_history)
        self.db.commit()
        self.db.refresh(work_orders_history)
        return work_orders_history

    def get_by_id(self, work_orders_history_id: int) -> Optional[WorkOrdersHistory]:
        """Get work_orders_history by id (primary key)"""
        return self.db.query(WorkOrdersHistory).filter(
            WorkOrdersHistory.id == work_orders_history_id,
        ).first()

    def get_by_status_like(self, status: str) -> List[WorkOrdersHistory]:
        """Get work_orders_historys by status (partial match)"""
        return self.db.query(WorkOrdersHistory).filter(
            WorkOrdersHistory.status.ilike(f"%{status}%"),
        ).all()

    def get_by_refnum_like(self, refnum: str) -> List[WorkOrdersHistory]:
        """Get work_orders_historys by refnum (partial match)"""
        return self.db.query(WorkOrdersHistory).filter(
            WorkOrdersHistory.refnum.ilike(f"%{refnum}%"),
        ).all()

    def get_by_created_by_like(self, created_by: str) -> List[WorkOrdersHistory]:
        """Get work_orders_historys by created_by (partial match)"""
        return self.db.query(WorkOrdersHistory).filter(
            WorkOrdersHistory.created_by.ilike(f"%{created_by}%"),
        ).all()

    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "id",
        order_desc: bool = False
    ) -> List[WorkOrdersHistory]:
        """Get all work_orders_historys with optional filtering and ordering"""
        query = self.db.query(WorkOrdersHistory)
        
        if filters:
            for key, value in filters.items():
                if hasattr(WorkOrdersHistory, key):
                    # Handle None values for nullable fields
                    if value is None:
                        query = query.filter(getattr(WorkOrdersHistory, key).is_(None))
                    else:
                        query = query.filter(getattr(WorkOrdersHistory, key) == value)
        
        # Apply ordering
        if hasattr(WorkOrdersHistory, order_by):
            order_column = getattr(WorkOrdersHistory, order_by)
            if order_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        else:
            # Fallback to default ordering by primary key
            if order_desc:
                query = query.order_by(desc(WorkOrdersHistory.id))
            else:
                query = query.order_by(asc(WorkOrdersHistory.id))
        
        return query.offset(skip).limit(limit).all()

    def update(self, work_orders_history_id: int, work_orders_history_data: Dict[str, Any]) -> Optional[WorkOrdersHistory]:
        """Update work_orders_history"""
        work_orders_history = self.get_by_id(work_orders_history_id)
        if not work_orders_history:
            return None
        
        # Only update allowed fields (exclude id)
        allowed_fields = [
            'status',
            'refid',
            'refnum',
            'refvalue',
            'created_at',
            'created_by',
        ]
        
        for key, value in work_orders_history_data.items():
            if hasattr(work_orders_history, key) and key in allowed_fields:
                setattr(work_orders_history, key, value)
        
        self.db.commit()
        self.db.refresh(work_orders_history)
        return work_orders_history

    def delete(self, work_orders_history_id: int) -> bool:
        """Delete work_orders_history (hard delete since no soft delete field)"""
        work_orders_history = self.get_by_id(work_orders_history_id)
        if not work_orders_history:
            return False
        
        self.db.delete(work_orders_history)
        self.db.commit()
        return True

    def search(
        self, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 100,
        order_by: str = "id",
        order_desc: bool = False
    ) -> List[WorkOrdersHistory]:
        """Search work_orders_historys by search term"""
        query = self.db.query(WorkOrdersHistory)
        
        if search_term:
            # Create OR conditions for all searchable columns
            from sqlalchemy import or_
            conditions = []
            conditions.append(WorkOrdersHistory.status.ilike(f"%{search_term}%"))
            conditions.append(WorkOrdersHistory.refnum.ilike(f"%{search_term}%"))
            conditions.append(WorkOrdersHistory.created_by.ilike(f"%{search_term}%"))
            
            if conditions:
                query = query.filter(or_(*conditions))
        else:
            # If no search term, return all
            pass
        
        # Apply ordering
        if hasattr(WorkOrdersHistory, order_by):
            order_column = getattr(WorkOrdersHistory, order_by)
            if order_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        else:
            if order_desc:
                query = query.order_by(desc(WorkOrdersHistory.id))
            else:
                query = query.order_by(asc(WorkOrdersHistory.id))
        
        return query.offset(skip).limit(limit).all()

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count work_orders_historys with optional filters"""
        query = self.db.query(WorkOrdersHistory)
        
        if filters:
            for key, value in filters.items():
                if hasattr(WorkOrdersHistory, key):
                    if value is None:
                        query = query.filter(getattr(WorkOrdersHistory, key).is_(None))
                    else:
                        query = query.filter(getattr(WorkOrdersHistory, key) == value)
        
        return query.count()

    def exists(self, work_orders_history_id: int) -> bool:
        """Check if work_orders_history exists"""
        return self.db.query(WorkOrdersHistory).filter(
            WorkOrdersHistory.id == work_orders_history_id
        ).first() is not None

    def get_status_values(self) -> List[str]:
        """Get list of all unique status values"""
        results = self.db.query(WorkOrdersHistory.status).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_refnum_values(self) -> List[str]:
        """Get list of all unique refnum values"""
        results = self.db.query(WorkOrdersHistory.refnum).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def get_created_by_values(self) -> List[str]:
        """Get list of all unique created_by values"""
        results = self.db.query(WorkOrdersHistory.created_by).distinct().all()
        return [row[0] for row in results if row[0] is not None]

    def bulk_create(self, work_orders_history_data_list: List[Dict[str, Any]]) -> List[WorkOrdersHistory]:
        """Create multiple work_orders_history records"""
        work_orders_historys = [WorkOrdersHistory(**data) for data in work_orders_history_data_list]
        self.db.add_all(work_orders_historys)
        self.db.commit()
        for work_orders_history in work_orders_historys:
            self.db.refresh(work_orders_history)
        return work_orders_historys

    def bulk_delete(self, work_orders_history_ids: List[int]) -> int:
        """Delete multiple work_orders_historys by IDs"""
        deleted_count = self.db.query(WorkOrdersHistory)\
            .filter(WorkOrdersHistory.id.in_(work_orders_history_ids))\
            .delete(synchronize_session=False)
        self.db.commit()
        return deleted_count