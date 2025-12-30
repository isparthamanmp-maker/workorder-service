from fastapi import Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.services.user_service import UserService
from src.services.work_orders_service import WorkOrdersService

# Use Depends properly
def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Get user service dependency"""
    return UserService(db)


def get_work_orders_service(db: Session = Depends(get_db)) -> WorkOrdersService:
    """Get work_orders service"""
    return WorkOrdersService(db)