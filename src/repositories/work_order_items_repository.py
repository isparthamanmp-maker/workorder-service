# src/repositories/work_order_items_repository.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.base import WorkOrderItems

class WorkOrderItemsRepository:
    """work_order_items repository with CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, item_data: Dict[str, Any]) -> WorkOrderItems:
        """Create a new work order item"""
        item = WorkOrderItems(**item_data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
    
    def create_bulk(self, items_data: List[Dict[str, Any]]) -> List[WorkOrderItems]:
        """Create multiple work order items"""
        items = []
        for item_data in items_data:
            item = WorkOrderItems(**item_data)
            self.db.add(item)
            items.append(item)
        self.db.commit()
        for item in items:
            self.db.refresh(item)
        return items
    
    def get_by_work_order_id(self, work_order_id: int) -> List[WorkOrderItems]:
        """Get all items for a work order"""
        return self.db.query(WorkOrderItems)\
            .filter(WorkOrderItems.work_order_id == work_order_id)\
            .order_by(WorkOrderItems.item_order)\
            .all()
    
    def delete_by_work_order_id(self, work_order_id: int) -> int:
        """Delete all items for a work order"""
        deleted_count = self.db.query(WorkOrderItems)\
            .filter(WorkOrderItems.work_order_id == work_order_id)\
            .delete(synchronize_session=False)
        self.db.commit()
        return deleted_count