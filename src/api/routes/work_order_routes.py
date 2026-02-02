# src/api/routes/work_orders_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import List, Optional
from src.services.work_orders_service import WorkOrdersService
from src.api.dependencies import get_work_orders_service
from src.schemas.work_orders_schema import WorkOrdersCreate, WorkOrdersUpdate, WorkOrdersResponse, WorkOrdersCreateRequest, WorkOrdersFullResponse, DocumentNumberResponse, WorkOrdersUpdateRequest
from datetime import datetime

router = APIRouter(prefix="/api/v1/work_orders", tags=["work_orders"])  # Fixed typo: work_orderss -> work_orders

@router.post("/", response_model=WorkOrdersResponse, status_code=status.HTTP_201_CREATED)
def create_work_orders(
    work_orders: WorkOrdersCreate,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Create a new work_orders record (simple version)"""
    try:
        created_work_orders = work_orders_service.create_work_orders(work_orders)
        return created_work_orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/complex", status_code=status.HTTP_201_CREATED)
def create_complex_work_order(
    request_data: WorkOrdersCreateRequest,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Create a new work order with complex payload (with work items)"""
    try:
        result = work_orders_service.create_work_order_from_request(request_data)
        return {
            "message": "Work order created successfully",
            "work_order_id": result["work_order"].id,
            "document_number": result["work_order"].document_number,
            "work_items_count": result["work_items_count"],
            "total_cost": result["total_cost"]
        }
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


# src/api/routes/work_orders_routes.py
# Add this route to the router

@router.get("/generate-document-number", response_model=DocumentNumberResponse)
def generate_document_number(
    submitted_by: str = Query(
        ..., 
        description="Department/person submitting (e.g., IT_Dept, Executive_Office, Ops_Support)"
    ),
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """
    Generate the next document number for a specific submitted_by department.
    
    Format: {number}/WOR/{submitted_by}:NMP/N/{currentyear}
    
    Example: 0009/WOR/IT_Dept:NMP/N/2025
    
    The number part is auto-incremented based on existing documents for the same
    submitted_by in the current year.
    """
    try:
        # Validate submitted_by is not empty
        if not submitted_by or not submitted_by.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="submitted_by parameter is required"
            )
        
        # Generate the document number
        document_number = work_orders_service.generate_next_document_number(submitted_by.strip())
        
        return DocumentNumberResponse(
            document_number=document_number,
            submitted_by=submitted_by,
            year=datetime.now().year
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating document number: {str(e)}"
        )
    
# In src/api/routes/work_orders_routes.py
@router.get("/{work_orders_id}", response_model=WorkOrdersFullResponse)  # Changed response model
def get_work_orders(
    work_orders_id: int = Path(..., ge=1, description="WorkOrders ID"),
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Get a single work_orders by ID (returns same structure as POST payload)"""
    # FIX: Changed from get_work_orderss (plural) to get_work_orders (singular)
    work_orders = work_orders_service.get_work_orders(work_orders_id)  # <-- Fixed here
    if not work_orders:
        raise HTTPException(status_code=404, detail="Work order not found")
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

@router.put("/{work_orders_id}/complex", status_code=status.HTTP_200_OK)
def update_complex_work_order(
    work_orders_id: int,
    request_data: WorkOrdersUpdateRequest,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Update an existing work order (accepts GET response structure)"""
    try:
        print("\n" + "=" * 80)
        print("UPDATE COMPLEX WORK ORDER CALLED")
        print(f"Work Order ID: {work_orders_id}")
        print("=" * 80)

        print(f"Type of request_data.supportingDocuments: {type(request_data.supportingDocuments)}")
        print(f"Type after dict(): {type(request_data.dict()['supportingDocuments'])}")
        
        # Convert to create request format
        print("Converting to create request format...")
        create_request = request_data.convert_to_create_request_format()
        
        print ("create_request:",create_request)
        # Convert supportingDocuments to dict BEFORE passing
        original_supporting_docs = request_data.dict()['supportingDocuments']
        
        print("\nConverted Create Request:")
        print(f"Total Cost: {create_request.totalCost}")
        
        # Update with special handling for files
        print("\nCalling update_work_order_with_existing_files...")
        result = work_orders_service.update_work_order_with_existing_files(
            work_orders_id, 
            create_request,
            request_data.dict()['supportingDocuments']  # Get the raw list
        )
        
        return {
            "message": "Work order updated successfully",
            "work_order_id": result["work_order"].id,
            "document_number": result["work_order"].document_number,
            "work_items_count": result["work_items_count"],
            "total_cost": result["total_cost"]
        }
    except Exception as e:
        print(f"\nERROR in update_complex_work_order: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{work_orders_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_orders(
    work_orders_id: int,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Delete work_orders"""
    if not work_orders_service.delete_work_orders(work_orders_id):
        raise HTTPException(status_code=404, detail=f"{pascal_name} not found")
    

@router.put("/{work_orders_id}/debug", status_code=status.HTTP_200_OK)
def debug_update_work_order(
    work_orders_id: int,
    request_data: WorkOrdersUpdateRequest,
    work_orders_service: WorkOrdersService = Depends(get_work_orders_service)
):
    """Debug endpoint to see what's in the payload"""
    import json
    from pprint import pprint
    
    print("=" * 80)
    print("DEBUG: Received PUT payload structure")
    print("=" * 80)
    
    # Show the structure
    data_dict = request_data.dict()
    
    print("\n1. SUPPORTING DOCUMENTS:")
    for i, doc in enumerate(data_dict.get('supportingDocuments', [])):
        print(f"\n  Document {i+1}: {doc.get('documentType')}")
        print(f"  Has Document: {doc.get('hasDocument')}")
        print(f"  Files count: {len(doc.get('files', []))}")
        
        for j, file in enumerate(doc.get('files', [])):
            print(f"\n    File {j+1}:")
            print(f"      fileName: {file.get('fileName')}")
            print(f"      fileId: {file.get('fileId')}")
            print(f"      action: {file.get('action')}")
            
            # Check for file content
            has_content = 'fileContent' in file or 'filecontent' in file
            content_length = 0
            if 'fileContent' in file:
                content_length = len(str(file.get('fileContent', '')))
            elif 'filecontent' in file:
                content_length = len(str(file.get('filecontent', '')))
            
            print(f"      Has fileContent: {has_content}")
            print(f"      Content length: {content_length}")
            
            if has_content and content_length > 0:
                # Show first 100 chars of content
                content = file.get('fileContent') or file.get('filecontent')
                # print(f"      Content preview: {str(content)[:100]}...")
    
    print("\n" + "=" * 80)
    print("Converted Create Request:")
    print("=" * 80)
    
    # Convert and show
    create_request = request_data.convert_to_create_request_format()
    
    # Parse attachments to see structure
    try:
        attachments = json.loads(create_request.supportingDocuments)
        print("\nAttachments JSON structure:")
        for field_name, section_data in attachments.items():
            print(f"\n{field_name}:")
            print(f"  uploaded: {section_data.get('uploaded')}")
            files = section_data.get('files', [])
            print(f"  files count: {len(files)}")
            
            for i, file in enumerate(files):
                print(f"\n  File {i+1}:")
                print(f"    filename: {file.get('filename')}")
                print(f"    action: {file.get('action')}")
                content = file.get('filecontent', '')
                print(f"    content length: {len(content)}")
                # if content:
                #     print(f"    content preview: {content[:50]}...")
    except Exception as e:
        print(f"Error parsing attachments: {e}")
    
    return {"message": "Debug info printed to console"}
