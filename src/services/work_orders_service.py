# src/services/work_orders_service.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models.base import WorkOrders, WorkOrderItems, WorkOrderVendors, SupportingDocuments
from src.schemas.work_orders_schema import WorkOrdersCreate, WorkOrdersUpdate, WorkOrdersCreateRequest
from fastapi import HTTPException
from sqlalchemy.orm import joinedload
from datetime import datetime


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
    
    def create_work_order_from_request(self, request_data: WorkOrdersCreateRequest) -> Dict[str, Any]:
        """Create work order from the complex request payload"""
        # Extract work order data
        work_order_data = request_data.extract_work_order_data()
        
        # Create work order
        work_order = WorkOrders(**work_order_data)
        self.db.add(work_order)
        self.db.flush()  # Flush to get the ID without committing
        
        # Extract and create attachmetns
        attachments_data = request_data.extract_attachments_data()
        for attachment_data in attachments_data:
            attachment_data['work_order_id'] = work_order.id
            attachment_item = SupportingDocuments(**attachment_data)
            self.db.add(attachment_item)

        
        # Extract and create work items
        work_items_data = request_data.extract_work_items_data()
        for item_data in work_items_data:
            item_data['work_order_id'] = work_order.id
            item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
            work_item = WorkOrderItems(**item_data)
            self.db.add(work_item)

        # Extract and create vendor data
        vendors_data = request_data.extract_vendor_data()
        for vendor_data in vendors_data:
            vendor_data['work_order_id'] = work_order.id
            work_vendor = WorkOrderVendors(**vendor_data)
            self.db.add(work_vendor)
        
        # Commit transaction
        self.db.commit()
        self.db.refresh(work_order)
        
        # Prepare response
        response = {
            "work_order": work_order,
            "work_items_count": len(work_items_data),
            "total_cost": request_data.totalCost
        }
        
        return response
    
    def update_work_order_from_request(self, work_orders_id: int, request_data: WorkOrdersCreateRequest) -> Dict[str, Any]:
        """Update existing work order from the complex request payload"""
        
        # First, get the existing work order
        existing_work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        
        if not existing_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        
        # Extract work order data for update
        work_order_data = request_data.extract_work_order_data()
        
        # Update the existing work order
        for key, value in work_order_data.items():
            if hasattr(existing_work_order, key):
                setattr(existing_work_order, key, value)
        
        # Update the updated_at timestamp
        existing_work_order.updated_at = datetime.utcnow()
        
        # Remove existing attachments and create new ones
        self.db.query(SupportingDocuments).filter(
            SupportingDocuments.work_order_id == work_orders_id
        ).delete()
        
        attachments_data = request_data.extract_attachments_data()
        for attachment_data in attachments_data:
            attachment_data['work_order_id'] = work_orders_id
            attachment_item = SupportingDocuments(**attachment_data)
            self.db.add(attachment_item)
        
        # Remove existing work items and create new ones
        self.db.query(WorkOrderItems).filter(
            WorkOrderItems.work_order_id == work_orders_id
        ).delete()
        
        work_items_data = request_data.extract_work_items_data()
        for item_data in work_items_data:
            item_data['work_order_id'] = work_orders_id
            item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
            work_item = WorkOrderItems(**item_data)
            self.db.add(work_item)
        
        # Remove existing vendor data and create new ones
        self.db.query(WorkOrderVendors).filter(
            WorkOrderVendors.work_order_id == work_orders_id
        ).delete()
        
        vendors_data = request_data.extract_vendor_data()
        for vendor_data in vendors_data:
            vendor_data['work_order_id'] = work_orders_id
            work_vendor = WorkOrderVendors(**vendor_data)
            self.db.add(work_vendor)
        
        # Commit transaction
        self.db.commit()
        self.db.refresh(existing_work_order)
        
        # Prepare response
        response = {
            "work_order": existing_work_order,
            "work_items_count": len(work_items_data),
            "total_cost": request_data.totalCost
        }
        
        return response
    
    def get_work_orders(self, work_orders_id: int) -> Optional[WorkOrders]:
        """Get work order with same structure as POST payload, plus id at root"""
    
        # Get work order with all relationships
        work_order = (
            self.db.query(WorkOrders)
            .options(
                joinedload(WorkOrders.work_items),
                joinedload(WorkOrders.vendors),
                joinedload(WorkOrders.supporting_documents)
            )
            .filter(WorkOrders.id == work_orders_id)
            .first()
        )
        
        if not work_order:
            return None
        
        # Build response matching POST request structure PLUS id at root
        response = {
            "id": work_order.id,  # Add this top-level id field
            "workOrder": {
                "id": work_order.id,
                "documentNumber": work_order.document_number,
                "requestDate": work_order.request_date.isoformat() if work_order.request_date else None,
                "requestType": work_order.request_type,
                "submittedBy": work_order.submitted_by,
                "scopeOfWorks": work_order.scope_of_works,
                "startDate": work_order.start_date.isoformat() if work_order.start_date else None,
                "endDate": work_order.end_date.isoformat() if work_order.end_date else None,
                "isUrgent": bool(work_order.is_urgent),
                "budgetStatus": work_order.budget_status,
                "costType": work_order.cost_type,
                "budgetIndex": work_order.budget_index,
                "budgetName": work_order.budget_name,
                "costEstimation": float(work_order.cost_estimation) if work_order.cost_estimation else None,
                "remainingBudget": float(work_order.remaining_budget) if work_order.remaining_budget else None,
                "underOver": work_order.under_over,
                "chargeToTenant": bool(work_order.charge_to_tenant),
                "recommendedContractor": work_order.recommended_contractor,
                "reason": work_order.reason,
                "vendorSelectionMethod": work_order.vendor_selection_method,
                "testAndAnalysis": work_order.test_and_analysis,
                "createdAt": work_order.created_at.isoformat() if work_order.created_at else None,
                "updatedAt": work_order.updated_at.isoformat() if work_order.updated_at else None
            },
            "workItems": [
                {
                    "id": item.id,
                    "workOrderId": item.work_order_id,
                    "description": item.description,
                    "quantity": float(item.quantity) if item.quantity else None,
                    "unitPrice": float(item.unit_price) if item.unit_price else None,
                    "totalPrice": float(item.total_price) if item.total_price else None,
                    "itemOrder": item.item_order
                }
                for item in work_order.work_items
            ],
            "tenderVendorData": [
                {
                    "id": vendor.id,
                    "workOrderId": vendor.work_order_id,
                    "vendorName": vendor.vendor_name
                }
                for vendor in work_order.vendors
            ],
            'supportingDocuments': [  # ADD THIS - transform supporting_documents
            {
                'id': doc.id,
                'workOrderId': doc.work_order_id,
                'documentType': doc.document_type,
                'hasDocument': bool(doc.has_document),
            }
            for doc in work_order.supporting_documents
        ],
            "totalCost": float(sum(
                item.quantity * item.unit_price 
                for item in work_order.work_items
            ))
        }
        
        return response
    
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