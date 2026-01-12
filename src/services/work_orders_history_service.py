# src/services/work_orders_history_service.py
from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.base import WorkOrdersHistory, WorkOrders
from src.schemas.work_orders_history_schema import WorkOrdersHistoryCreate, WorkOrdersHistoryUpdate

import datetime
import os

class WorkOrdersHistoryService:
    """work_orders_history service layer using Pydantic schemas"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_work_orders_history(self, work_orders_history_data: WorkOrdersHistoryCreate) -> WorkOrdersHistory:
        try:

            """Create a new work_orders_history record from Pydantic schema and update work order status to 'Submit'"""
            # Convert schema to dict (handles aliases)
            work_orders_history_dict = work_orders_history_data.model_dump(by_alias=True)
            
            # Create new work_orders_history
            work_orders_history = WorkOrdersHistory(**work_orders_history_dict)
            
            # Update the related work order status to 'Submit'
            # Assuming work_orders_history has a work_order_id field that references the work order
            if hasattr(work_orders_history, 'refid') and work_orders_history.refid:
                work_order = self.db.query(WorkOrders).filter(
                    WorkOrders.id == work_orders_history.refid
                ).first()
                
                if work_order:
                    work_order.status = work_orders_history.status
                    # Optionally, update the updated_at timestamp
                    work_order.updated_at = datetime.datetime.now()

                    if work_orders_history.status=='Cancel':
                        # Make budget API call
                        import requests
                        import json

                        url = f'{os.getenv("BUDGET_SERVICE")}/api/v1/budget_final_realisasis/'
                        print(url)
                        payload = json.dumps({
                            "budget_index": work_order.budget_index,
                            "refid": work_order.id,
                            "refnum": work_order.document_number,
                            "refvalue": float(work_order.cost_estimation*-1),  # Convert to float
                            "created_by": "Ketut Sakho Parthama"
                        })
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        
                        response = requests.request("POST", url, headers=headers, data=payload)
                        
                        # Check if API call was successful
                        if response.status_code not in [200, 201]:
                            raise Exception(f"Budget API call failed with status {response.status_code}: {response.text}")
                    
            
            self.db.add(work_orders_history)
            self.db.commit()
            self.db.refresh(work_orders_history)
            return work_orders_history
        
        except requests.exceptions.RequestException as e:
            # Rollback database transaction on API call failure
            self.db.rollback()
            raise Exception(f"Failed to call budget API: {str(e)}")
            
        except Exception as e:
            # Rollback database transaction on any other error
            self.db.rollback()
            # Log the error for debugging
            print(f"Error creating work order: {str(e)}")
            # Re-raise the exception or handle it as needed
            raise Exception(f"Failed to create work order: {str(e)}")
    
    def get_work_orders_history(self, work_orders_history_id: int) -> Optional[WorkOrdersHistory]:
        """Get work_orders_history by ID"""
        return self.db.query(WorkOrdersHistory).filter(WorkOrdersHistory.id == work_orders_history_id).first()
    
    def get_work_orders_historys(self, skip: int = 0, limit: int = 100, order_by: str = "id") -> List[WorkOrdersHistory]:
        """Get work_orders_historys with pagination and ordering"""
        # Map the alias to actual column names
        order_column_map = {
            "id": WorkOrdersHistory.id,
            "status": WorkOrdersHistory.status,
            "refid": WorkOrdersHistory.refid,
            "refnum": WorkOrdersHistory.refnum,
            "refvalue": WorkOrdersHistory.refvalue,
            "created_at": WorkOrdersHistory.created_at,
            "created_by": WorkOrdersHistory.created_by,
        }
        
        # Get the column to order by (default to id)
        order_column = order_column_map.get(order_by, WorkOrdersHistory.id)
        
        return self.db.query(WorkOrdersHistory)\
            .order_by(order_column)\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    def update_work_orders_history(self, work_orders_history_id: int, work_orders_history_data: WorkOrdersHistoryUpdate) -> Optional[WorkOrdersHistory]:
        """Update work_orders_history record from Pydantic schema"""
        work_orders_history = self.db.query(WorkOrdersHistory).filter(WorkOrdersHistory.id == work_orders_history_id).first()
        if not work_orders_history:
            return None
        
        # Convert schema to dict (exclude unset fields)
        update_dict = work_orders_history_data.model_dump(exclude_unset=True, by_alias=True)
        
        # Update fields
        for key, value in update_dict.items():
            if hasattr(work_orders_history, key):
                setattr(work_orders_history, key, value)
        
        self.db.commit()
        self.db.refresh(work_orders_history)
        return work_orders_history
    
    def delete_work_orders_history(self, work_orders_history_id: int) -> bool:
        """Delete work_orders_history record"""
        work_orders_history = self.db.query(WorkOrdersHistory).filter(WorkOrdersHistory.id == work_orders_history_id).first()
        if not work_orders_history:
            return False
        
        self.db.delete(work_orders_history)
        self.db.commit()
        return True
    
    def search_work_orders_historys(self, search_term: str, skip: int = 0, limit: int = 100) -> List[WorkOrdersHistory]:
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
        
        return query.order_by(WorkOrdersHistory.id).offset(skip).limit(limit).all()
    
    def count_work_orders_historys(self) -> int:
        """Count total work_orders_history records"""
        return self.db.query(WorkOrdersHistory).count()