# src/repositories/work_order_vendors_repository.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.base import WorkOrderVendors

class WorkOrderVendorsRepository:
    """work_order_vendors repository with CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, vendor_data: Dict[str, Any]) -> WorkOrderVendors:
        """Create a new work order vendor"""
        vendor = WorkOrderVendors(**vendor_data)
        self.db.add(vendor)
        self.db.commit()
        self.db.refresh(vendor)
        return vendor
    
    def create_bulk(self, vendors_data: List[Dict[str, Any]]) -> List[WorkOrderVendors]:
        """Create multiple work order vendors"""
        vendors = []
        for vendor_data in vendors_data:
            vendor = WorkOrderVendors(**vendor_data)
            self.db.add(vendor)
            vendors.append(vendor)
        self.db.commit()
        for vendor in vendors:
            self.db.refresh(vendor)
        return vendors
    
    def get_by_work_order_id(self, work_order_id: int) -> List[WorkOrderVendors]:
        """Get all vendors for a work order"""
        return self.db.query(WorkOrderVendors)\
            .filter(WorkOrderVendors.work_order_id == work_order_id)\
            .order_by(WorkOrderVendors.vendor_order)\
            .all()
    
    def delete_by_work_order_id(self, work_order_id: int) -> int:
        """Delete all vendors for a work order"""
        deleted_count = self.db.query(WorkOrderVendors)\
            .filter(WorkOrderVendors.work_order_id == work_order_id)\
            .delete(synchronize_session=False)
        self.db.commit()
        return deleted_count