# src/api/routes/work_orders_history_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import List, Optional
from src.services.work_orders_history_service import WorkOrdersHistoryService
from src.api.dependencies import get_work_orders_history_service
from src.schemas.work_orders_history_schema import WorkOrdersHistoryCreate, WorkOrdersHistoryUpdate, WorkOrdersHistoryResponse

router = APIRouter(prefix="/api/v1/work_orders_historys", tags=["work_orders_historys"])

@router.post("/", response_model=WorkOrdersHistoryResponse, status_code=status.HTTP_201_CREATED)
def create_work_orders_history(
    work_orders_history: WorkOrdersHistoryCreate,
    work_orders_history_service: WorkOrdersHistoryService = Depends(get_work_orders_history_service)
):
    """Create a new work_orders_history record"""
    try:
        created_work_orders_history = work_orders_history_service.create_work_orders_history(work_orders_history)
        return created_work_orders_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=List[WorkOrdersHistoryResponse])
def get_work_orders_historys(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description=f"Search in status, refnum, created_by"),
    work_orders_history_service: WorkOrdersHistoryService = Depends(get_work_orders_history_service)
):
    """Get all work_orders_historys with pagination and search"""
    if search:
        return work_orders_history_service.search_work_orders_historys(search, skip, limit)
    return work_orders_history_service.get_work_orders_historys(skip, limit)

@router.get("/{work_orders_history_id}", response_model=WorkOrdersHistoryResponse)
def get_work_orders_history(
    work_orders_history_id: int = Path(..., ge=1, description="WorkOrdersHistory ID"),
    work_orders_history_service: WorkOrdersHistoryService = Depends(get_work_orders_history_service)
):
    """Get a single work_orders_history by ID"""
    work_orders_history = work_orders_history_service.get_work_orders_history(work_orders_history_id)
    if not work_orders_history:
        raise HTTPException(status_code=404, detail=f"{pascal_name} not found")
    return work_orders_history

@router.put("/{work_orders_history_id}", response_model=WorkOrdersHistoryResponse)
def update_work_orders_history(
    work_orders_history_id: int,
    work_orders_history_update: WorkOrdersHistoryUpdate,
    work_orders_history_service: WorkOrdersHistoryService = Depends(get_work_orders_history_service)
):
    """Update work_orders_history"""
    try:
        updated_work_orders_history = work_orders_history_service.update_work_orders_history(work_orders_history_id, work_orders_history_update)
        if not updated_work_orders_history:
            raise HTTPException(status_code=404, detail=f"{pascal_name} not found")
        return updated_work_orders_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{work_orders_history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_orders_history(
    work_orders_history_id: int,
    work_orders_history_service: WorkOrdersHistoryService = Depends(get_work_orders_history_service)
):
    """Delete work_orders_history"""
    if not work_orders_history_service.delete_work_orders_history(work_orders_history_id):
        raise HTTPException(status_code=404, detail=f"{pascal_name} not found")