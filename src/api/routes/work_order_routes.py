# src/api/routes/work_orders_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import List, Optional
from src.services.work_orders_service import WorkOrdersService
from src.api.dependencies import get_work_orders_service
from src.schemas.work_orders_schema import WorkOrdersCreate, WorkOrdersUpdate, WorkOrdersResponse

router = APIRouter(prefix="/api/v1/work_orderss", tags=["work_orderss"])

@router.post("/", response_model=WorkOrdersResponse, status_code=status.HTTP_201_CREATED)
def create_work_orders(
    work_orders: WorkOrdersCreate,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Create a new work_orders record"""
    try:
        created_work_orders = work_orders_service.create_work_orders(work_orders)
        return created_work_orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=List[WorkOrdersResponse])
def get_work_orderss(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description=f"Search in document_number, scope_of_works, budget_index"),
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Get all work_orderss with pagination and search"""
    if search:
        return work_orders_service.search_work_orderss(search, skip, limit)
    return work_orders_service.get_work_orderss(skip, limit)

@router.get("/{work_orders_id}", response_model=WorkOrdersResponse)
def get_work_orders(
    work_orders_id: int = Path(..., ge=1, description="WorkOrders ID"),
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Get a single work_orders by ID"""
    work_orders = work_orders_service.get_work_orders(work_orders_id)
    if not work_orders:
        raise HTTPException(status_code=404, detail=f"{pascal_name} not found")
    return work_orders

@router.put("/{work_orders_id}", response_model=WorkOrdersResponse)
def update_work_orders(
    work_orders_id: int,
    work_orders_update: WorkOrdersUpdate,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Update work_orders"""
    try:
        updated_work_orders = work_orders_service.update_work_orders(work_orders_id, work_orders_update)
        if not updated_work_orders:
            raise HTTPException(status_code=404, detail=f"{pascal_name} not found")
        return updated_work_orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{work_orders_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_orders(
    work_orders_id: int,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Delete work_orders"""
    if not work_orders_service.delete_work_orders(work_orders_id):
        raise HTTPException(status_code=404, detail=f"{pascal_name} not found")