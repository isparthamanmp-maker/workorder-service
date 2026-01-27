from typing import List, Optional, Dict, Any, Tuple  # Add Tuple here
from sqlalchemy.orm import Session
from src.models.base import WorkOrders, WorkOrderItems, WorkOrderVendors, SupportingDocuments, Authorizations, WorkOrderFiles
from src.schemas.work_orders_schema import WorkOrdersCreate, WorkOrdersUpdate, WorkOrdersCreateRequest
from fastapi import HTTPException
from sqlalchemy.orm import joinedload
from datetime import datetime
import requests
import json
import os
import io
import binascii
from minio import Minio
from minio.error import S3Error
import base64 

class WorkOrdersService:
    """work_orders service layer using Pydantic schemas"""
    
    def __init__(self, db: Session):
        self.db = db
        # Initialize MinIO client
        self.minio_client = Minio(
            endpoint="10.10.1.7:9000",
            access_key="minioadmin",
            secret_key="StrongPasswordHere123",
            secure=False
        )
        self.bucket_name = "workorder"
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Check if bucket exists, create if not"""
        try:
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                print(f"Bucket '{self.bucket_name}' created successfully")
        except S3Error as e:
            print(f"Error ensuring bucket exists: {e}")
    
    def _upload_to_minio(self, work_order_number: str, file_name: str, file_content: str) -> tuple[str, int]:
        """Upload file to MinIO with structure: bucketname/workordernumber/filename"""
        try:
            print(f"\n  DEBUG _upload_to_minio called:")
            print(f"    Work order number: {work_order_number}")
            print(f"    File name: {file_name}")
            print(f"    Content length: {len(file_content)}")
            print(f"    First 100 chars: {file_content[:100]}...")
            
            # Clean content
            file_content_clean = file_content.replace(" ", "").replace("\n", "").replace("\r", "")
            print(f"    Cleaned length: {len(file_content_clean)}")
            
            if len(file_content_clean) < 10:
                raise Exception(f"File content too short: {len(file_content_clean)} chars")
            
            # Determine if content is hex or base64
            file_bytes = None
            
            # Check if it's hex (only contains 0-9, a-f, A-F)
            import re
            hex_pattern = re.compile(r'^[0-9a-fA-F]+$')
            
            if hex_pattern.match(file_content_clean):
                print(f"    Detected: HEX format")
                try:
                    file_bytes = binascii.unhexlify(file_content_clean)
                    print(f"    Successfully decoded hex to {len(file_bytes)} bytes")
                except binascii.Error as e:
                    print(f"    ERROR: Invalid hex: {e}")
                    raise
            else:
                # Try as Base64
                print(f"    Detected: BASE64 format (or other)")
                try:
                    import base64
                    # Try standard base64 decode
                    file_bytes = base64.b64decode(file_content_clean)
                    print(f"    Successfully decoded base64 to {len(file_bytes)} bytes")
                except Exception as e:
                    print(f"    ERROR: Not valid base64: {e}")
                    # Try URL-safe base64
                    try:
                        file_bytes = base64.urlsafe_b64decode(file_content_clean + '=' * (-len(file_content_clean) % 4))
                        print(f"    Successfully decoded URL-safe base64 to {len(file_bytes)} bytes")
                    except Exception as e2:
                        print(f"    ERROR: Not valid URL-safe base64 either: {e2}")
                        raise Exception(f"Content is neither valid hex nor base64: {str(e)}")
            
            # Convert to file-like object
            file_data = io.BytesIO(file_bytes)
            file_size = len(file_bytes)
            
            # Create safe filename
            safe_file_name = file_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            
            # Object name: workordernumber/filename
            object_name = f"{work_order_number}/{safe_file_name}"
            print(f"    Object name: {object_name}")
            
            # Upload to MinIO
            print(f"    Attempting MinIO upload...")
            self.minio_client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=self._get_content_type(file_name)
            )
            
            # Generate URL
            url = f"http://10.10.1.7:9000/{self.bucket_name}/{object_name}"
            print(f"    ✓ Upload successful!")
            print(f"    URL: {url}")
            print(f"    Size: {file_size} bytes")
            
            return url, file_size
            
        except Exception as e:
            print(f"    ✗ Upload failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _get_content_type(self, file_name: str) -> str:
        """Get content type based on file extension"""
        ext = os.path.splitext(file_name)[1].lower()
        
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
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
        try:
            # Extract work order data
            work_order_data = request_data.extract_work_order_data()
            
            # Create work order
            work_order = WorkOrders(**work_order_data)
            self.db.add(work_order)
            self.db.flush()  # Flush to get the ID without committing
            
            # Store work order number
            work_order_number = work_order.document_number
            
            # Make budget API call
            url = f'{os.getenv("BUDGET_SERVICE")}/api/v1/budget_final_realisasis/'
            payload = json.dumps({
                "budget_index": work_order.budget_index,
                "refid": work_order.id,
                "refnum": work_order.document_number,
                "refvalue": work_order.cost_estimation,
                "created_by": "Ketut Sakho Parthama"
            })
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.request("POST", url, headers=headers, data=payload)
            
            # Check if API call was successful
            if response.status_code not in [200, 201]:
                raise Exception(f"Budget API call failed with status {response.status_code}: {response.text}")
            
            # Process attachments and files with work order number
            self._process_attachments_and_files(request_data, work_order.id, work_order_number)

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
            
            # Extract and create authorizations data
            authorizations_data = request_data.extract_authorizations_data()
            for auth_data in authorizations_data:
                auth_data['work_order_id'] = work_order.id
                authorization = Authorizations(**auth_data)
                self.db.add(authorization)

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
            
        except requests.exceptions.RequestException as e:
            # Rollback database transaction on API call failure
            self.db.rollback()
            raise Exception(f"Failed to call budget API: {str(e)}")
            
        except Exception as e:
            # Rollback database transaction on any other error
            self.db.rollback()
            print(f"Error creating work order: {str(e)}")
            raise Exception(f"Failed to create work order: {str(e)}")
    
    def _process_attachments_and_files(self, request_data: WorkOrdersCreateRequest, work_order_id: int, work_order_number: str):
        """Process attachments and upload files to MinIO - DEBUG VERSION"""
        try:
            print("=" * 80)
            print("DEBUG: Starting file processing")
            print(f"Work Order ID: {work_order_id}")
            print(f"Work Order Number: {work_order_number}")
            
            # Parse attachments
            attachments = json.loads(request_data.attachments)
            print(f"\nDEBUG: Parsed attachments JSON keys: {list(attachments.keys())}")
            
            # Print full structure for debugging
            print(f"\nDEBUG: Full attachments structure:")
            print(json.dumps(attachments, indent=2))
            print("=" * 80)
            
            total_files_processed = 0
            
            # Process each attachment type
            for field_name, section_data in attachments.items():
                print(f"\n{'='*40}")
                print(f"Processing field: {field_name}")
                print(f"Section data type: {type(section_data)}")
                
                if isinstance(section_data, dict):
                    print(f"Section data keys: {list(section_data.keys())}")
                    
                    # Check if uploaded
                    if section_data.get('uploaded', False):
                        print(f"✓ {field_name} is marked as uploaded")
                        
                        # Check for files
                        if 'files' in section_data:
                            files = section_data['files']
                            print(f"Files type: {type(files)}")
                            
                            if isinstance(files, list):
                                print(f"Number of files: {len(files)}")
                                
                                # Create supporting document
                                document_type = field_name  # Use field name as document type
                                supporting_doc = SupportingDocuments(
                                    work_order_id=work_order_id,
                                    document_type=document_type,
                                    has_document=True
                                )
                                self.db.add(supporting_doc)
                                self.db.flush()
                                
                                # Debug: Print all file items
                                for i, item in enumerate(files):
                                    print(f"\nFile item {i}:")
                                    print(f"  Type: {type(item)}")
                                    if isinstance(item, dict):
                                        print(f"  Keys: {list(item.keys())}")
                                        for key, value in item.items():
                                            if key == 'filecontent':
                                                print(f"  {key}: {str(value)[:100]}...")
                                            else:
                                                print(f"  {key}: {value}")
                                    else:
                                        print(f"  Value: {item}")
                                
                                # Try to process files based on structure
                                processed_in_this_section = self._process_files_list(
                                    files, work_order_id, work_order_number, supporting_doc.id
                                )
                                total_files_processed += processed_in_this_section
                                print(f"✓ Processed {processed_in_this_section} files in {field_name}")
                            else:
                                print(f"✗ Files is not a list: {type(files)}")
                        else:
                            print(f"✗ No files key in section data")
                            
                            # Still create supporting document if uploaded
                            document_type = field_name
                            supporting_doc = SupportingDocuments(
                                work_order_id=work_order_id,
                                document_type=document_type,
                                has_document=False
                            )
                            self.db.add(supporting_doc)
                    else:
                        print(f"✗ {field_name} is not uploaded")
                else:
                    print(f"✗ Section data is not a dict")
            
            print(f"\n{'='*80}")
            print(f"DEBUG: Total files processed across all sections: {total_files_processed}")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n✗ ERROR in _process_attachments_and_files: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _process_files_list(self, files: list, work_order_id: int, work_order_number: str, supporting_doc_id: int) -> int:
        """Process a list of files - try different structures"""
        processed_count = 0
        
        # Strategy 1: Each item has both filename and filecontent
        for i, item in enumerate(files):
            if isinstance(item, dict) and 'filename' in item and 'filecontent' in item:
                file_name = item['filename']
                file_content = item['filecontent']
                
                if file_name and file_content:
                    try:
                        file_url, file_size = self._upload_to_minio(work_order_number, file_name, file_content)
                        
                        work_order_file = WorkOrderFiles(
                            work_order_id=work_order_id,
                            supporting_document_id=supporting_doc_id,
                            file_name=file_name,
                            file_url=file_url,
                            file_size=file_size
                        )
                        self.db.add(work_order_file)
                        processed_count += 1
                        print(f"  ✓ Uploaded via Strategy 1: {file_name}")
                    except Exception as e:
                        print(f"  ✗ Failed to upload {file_name}: {e}")
        
        # If Strategy 1 didn't work, try Strategy 2: Paired items
        if processed_count == 0:
            print("  Trying Strategy 2: Paired items (filename, filecontent)...")
            for i in range(0, len(files) - 1, 2):
                if i + 1 < len(files):
                    file_item = files[i]
                    content_item = files[i + 1]
                    
                    file_name = None
                    file_content = None
                    
                    # Extract filename from first item
                    if isinstance(file_item, dict) and 'filename' in file_item:
                        file_name = file_item['filename']
                    elif isinstance(file_item, str):
                        file_name = file_item
                    
                    # Extract filecontent from second item
                    if isinstance(content_item, dict) and 'filecontent' in content_item:
                        file_content = content_item['filecontent']
                    elif isinstance(content_item, str):
                        file_content = content_item
                    
                    if file_name and file_content:
                        try:
                            file_url, file_size = self._upload_to_minio(work_order_number, file_name, file_content)
                            
                            work_order_file = WorkOrderFiles(
                                work_order_id=work_order_id,
                                supporting_document_id=supporting_doc_id,
                                file_name=file_name,
                                file_url=file_url,
                                file_size=file_size
                            )
                            self.db.add(work_order_file)
                            processed_count += 1
                            print(f"  ✓ Uploaded via Strategy 2: {file_name}")
                        except Exception as e:
                            print(f"  ✗ Failed to upload {file_name}: {e}")
        
        return processed_count
    

    def _delete_files_from_minio(self, work_order_number: str, files: List[WorkOrderFiles] = None):
        """
        Delete files from MinIO storage using the structure: bucketname/workordernumber/filename
        
        Args:
            work_order_number: The work order number (document_number)
            files: Optional list of WorkOrderFiles objects (if None, will find all files for this work order)
        """
        try:
            if not work_order_number:
                print("⚠ No work order number provided for MinIO deletion")
                return
            
            # If files list is not provided, query from database
            if files is None:
                files = self.db.query(WorkOrderFiles).filter(
                    WorkOrderFiles.work_order_id == self._get_work_order_id_by_number(work_order_number)
                ).all()
            
            deleted_count = 0
            error_count = 0
            
            # Delete individual files
            for file in files:
                try:
                    # Construct object name: workordernumber/filename
                    object_name = f"{work_order_number}/{file.file_name}"
                    
                    # Check if object exists
                    try:
                        self.minio_client.stat_object(self.bucket_name, object_name)
                        
                        # Delete the file
                        self.minio_client.remove_object(
                            bucket_name=self.bucket_name,
                            object_name=object_name
                        )
                        print(f"✓ Deleted from MinIO: {object_name}")
                        deleted_count += 1
                        
                    except S3Error as e:
                        if e.code == 'NoSuchKey':
                            print(f"⚠ File not found in MinIO: {object_name}")
                        else:
                            print(f"⚠ Error checking file in MinIO: {object_name} - {e}")
                            error_count += 1
                            
                except Exception as e:
                    print(f"✗ Error processing file deletion for {file.file_name}: {e}")
                    error_count += 1
            
            # Also try to delete the entire directory if it exists
            try:
                # List all objects with this prefix
                objects = self.minio_client.list_objects(
                    self.bucket_name,
                    prefix=f"{work_order_number}/",
                    recursive=True
                )
                
                dir_objects = list(objects)
                if dir_objects:
                    print(f"Found {len(dir_objects)} objects in directory {work_order_number}/")
                    
            except Exception as e:
                print(f"Note: Could not list directory {work_order_number}/: {e}")
            
            print(f"MinIO cleanup complete: {deleted_count} deleted, {error_count} errors")
            
        except Exception as e:
            print(f"✗ Error in MinIO deletion process: {e}")

    def _get_work_order_id_by_number(self, work_order_number: str) -> Optional[int]:
        """Helper method to get work order ID by document number"""
        work_order = self.db.query(WorkOrders).filter(
            WorkOrders.document_number == work_order_number
        ).first()
        return work_order.id if work_order else None
                
    def update_work_order_from_request(self, work_orders_id: int, request_data: WorkOrdersCreateRequest) -> Dict[str, Any]:
        """Update existing work order from the complex request payload"""
        
        # First, get the existing work order
        existing_work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        
        if not existing_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        
        try:
            # Extract work order data for update
            work_order_data = request_data.extract_work_order_data()
            
            # Store the current work order number before update
            current_work_order_number = existing_work_order.document_number
            
            # Update the existing work order
            for key, value in work_order_data.items():
                if hasattr(existing_work_order, key):
                    setattr(existing_work_order, key, value)
            
            # Update the updated_at timestamp
            existing_work_order.updated_at = datetime.utcnow()
            
            # --- DELETE EXISTING FILES FROM MINIO ---
            # Delete files using work order number
            print(f"Deleting MinIO files for work order: {current_work_order_number}")
            self._delete_files_from_minio(current_work_order_number)
            
            # --- DELETE DATABASE RECORDS ---
            
            # 1. Get all files first (for potential backup/recovery)
            existing_files = self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
            ).all()
            
            # 2. Delete work_order_files
            self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            # 3. Delete supporting_documents
            self.db.query(SupportingDocuments).filter(
                SupportingDocuments.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            # 4. Delete other related records
            self.db.query(WorkOrderItems).filter(
                WorkOrderItems.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            self.db.query(WorkOrderVendors).filter(
                WorkOrderVendors.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            self.db.query(Authorizations).filter(
                Authorizations.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            # Flush to apply deletions
            self.db.flush()
            
            # --- PROCESS NEW FILES ---
            # Need to update the _upload_to_minio method to use workordernumber/filename structure
            self._process_attachments_and_files(request_data, work_orders_id, existing_work_order.document_number)
            
            # Extract and create work items
            work_items_data = request_data.extract_work_items_data()
            for item_data in work_items_data:
                item_data['work_order_id'] = work_orders_id
                item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
                work_item = WorkOrderItems(**item_data)
                self.db.add(work_item)
            
            # Extract and create vendor data
            vendors_data = request_data.extract_vendor_data()
            for vendor_data in vendors_data:
                vendor_data['work_order_id'] = work_orders_id
                work_vendor = WorkOrderVendors(**vendor_data)
                self.db.add(work_vendor)
            
            # Extract and create authorizations data
            authorizations_data = request_data.extract_authorizations_data()
            for auth_data in authorizations_data:
                auth_data['work_order_id'] = work_orders_id
                authorization = Authorizations(**auth_data)
                self.db.add(authorization)
                
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
        
        except Exception as e:
            self.db.rollback()
            print(f"Error updating work order: {str(e)}")
            raise Exception(f"Failed to update work order: {str(e)}")
    
    def get_work_orders(self, work_orders_id: int) -> Optional[WorkOrders]:
        """Get work order with same structure as POST payload, plus id at root"""
    
        # Get work order with all relationships
        work_order = (
            self.db.query(WorkOrders)
            .options(
                joinedload(WorkOrders.work_items),
                joinedload(WorkOrders.vendors),
                joinedload(WorkOrders.supporting_documents),
                joinedload(WorkOrders.authorizations),
                joinedload(WorkOrders.files)
            )
            .filter(WorkOrders.id == work_orders_id)
            .first()
        )
        
        if not work_order:
            return None
        
        # Build response matching POST request structure PLUS id at root
        response = {
            "id": work_order.id,
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
                "updatedAt": work_order.updated_at.isoformat() if work_order.updated_at else None,
                "status": work_order.status,
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
            'supportingDocuments': [
                {
                    'id': doc.id,
                    'workOrderId': doc.work_order_id,
                    'documentType': doc.document_type,
                    'hasDocument': bool(doc.has_document),
                    'files': [
                        {
                            'id': file.id,
                            'fileName': file.file_name,
                            'fileUrl': file.file_url,
                            'fileSize': file.file_size,
                            'uploadDate': file.upload_date.isoformat() if file.upload_date else None
                        }
                        for file in doc.files
                    ]
                }
                for doc in work_order.supporting_documents
            ],
            'files': [
                {
                    'id': file.id,
                    'workOrderId': file.work_order_id,
                    'supportingDocumentId': file.supporting_document_id,
                    'fileName': file.file_name,
                    'fileUrl': file.file_url,
                    'fileSize': file.file_size,
                    'uploadDate': file.upload_date.isoformat() if file.upload_date else None
                }
                for file in work_order.files
            ],
            'authorizations': [self._format_authorizations_response(work_order.authorizations)],
            "totalCost": float(sum(
                item.quantity * item.unit_price 
                for item in work_order.work_items
            ))
        }
        
        return response
    
    def _format_authorizations_response(self, authorizations: List[Authorizations]) -> Dict[str, Any]:
        """Format authorizations data back to the original payload format"""
        # Initialize with empty values
        formatted = {
            "preparedBy": "",
            "preparedDate": "",
            "deptHeadName": "",
            "deptHeadDate": "",
            "accDeptName": "",
            "accDeptDate": "",
            "bmName": "",
            "bmDate": "",
            "directorName": "",
            "directorDate": "",
            "purchasingName": "",
            "purchasingDate": ""
        }
        
        # Mapping between authorization_type and form field names
        auth_mapping = {
            'prepared_by': ('preparedBy', 'preparedDate'),
            'dept_head': ('deptHeadName', 'deptHeadDate'),
            'verified_by_acc_dept': ('accDeptName', 'accDeptDate'),
            'approved_by_bm': ('bmName', 'bmDate'),
            'approved_by_director': ('directorName', 'directorDate'),
            'received_by_purchasing': ('purchasingName', 'purchasingDate')
        }
        
        for auth in authorizations:
            if auth.authorization_type in auth_mapping:
                name_field, date_field = auth_mapping[auth.authorization_type]
                formatted[name_field] = auth.person_name or ""
                formatted[date_field] = auth.authorization_date.isoformat() if auth.authorization_date else ""
        
        return formatted
    
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
        """Delete work_orders record and all associated files from MinIO"""
        work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        if not work_order:
            return False
        
        try:
            # Get work order number before deletion
            work_order_number = work_order.document_number
            
            # Delete files from MinIO using work order number
            print(f"Deleting MinIO files for work order: {work_order_number}")
            self._delete_files_from_minio(work_order_number)
            
            # Delete database records
            self.db.delete(work_order)
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting work order {work_orders_id}: {e}")
            raise Exception(f"Failed to delete work order: {str(e)}")
    
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
    
    def generate_next_document_number(self, submitted_by: str) -> str:
        """
        Generate the next document number in format: {number}/WOR/{submitted_by}:NMP/N/{currentyear}
        
        Based on existing data:
        - Format: {number}/WOR/{submitted_by}:NMP/N/{YYYY}
        - Example: 0009/WOR/IT_Dept:NMP/N/2025
        
        Rules:
        1. Get the highest number for the current year and submitted_by
        2. Increment by 1
        3. Pad with leading zeros to 4 digits
        """
        from sqlalchemy import extract
        
        current_year = datetime.now().year
        
        # Query for the highest document number for this submitted_by in current year
        query = self.db.query(WorkOrders.document_number).filter(
            WorkOrders.submitted_by == submitted_by,
            extract('year', WorkOrders.request_date) == current_year
        ).all()
        
        max_number = 0
        
        for doc_num_row in query:
            doc_num = doc_num_row[0]
            if doc_num:
                # Extract the number part (before the first slash)
                # Expected format: 0009/WOR/IT_Dept:NMP/N/2025
                parts = doc_num.split('/')
                if len(parts) > 0 and parts[0].isdigit():
                    number_part = int(parts[0])
                    if number_part > max_number:
                        max_number = number_part
        
        # If no existing documents found for this submitted_by in current year, start from 1
        next_number = max_number + 1
        
        # Format with leading zeros (4 digits)
        number_str = f"{next_number:04d}"
        
        # Construct the new document number
        # Format: {number}/WOR/{submitted_by}:NMP/N/{currentyear}
        new_document_number = f"{number_str}/WOR/{submitted_by}:NMP/N/{current_year}"
        
        return new_document_number

    def update_work_order_with_existing_files(self, work_orders_id: int, request_data: WorkOrdersCreateRequest, original_supporting_docs: List[dict]) -> Dict[str, Any]:
        """Update work order but preserve existing files marked as 'existing'"""
        
        # Get existing work order
        existing_work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        
        if not existing_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        
        try:
            # Extract work order data for update
            work_order_data = request_data.extract_work_order_data()
            
            # Update work order fields
            for key, value in work_order_data.items():
                if hasattr(existing_work_order, key):
                    setattr(existing_work_order, key, value)
            
            existing_work_order.updated_at = datetime.utcnow()
            
            # Store work order number
            work_order_number = existing_work_order.document_number
            
            # --- DELETE ONLY NEW/MODIFIED FILES, KEEP EXISTING ONES ---
            
            # Parse attachments to find which files to keep
            attachments = json.loads(request_data.attachments)
            
            # Create a map of files to keep (based on action field)
            files_to_keep = []
            for doc in original_supporting_docs:
                for file in doc.get("files", []):
                    if file.get("action") == "existing":
                        files_to_keep.append({
                            "file_name": file.get("fileName", ""),
                            "file_url": f"http://10.10.1.7:9000/{self.bucket_name}/{work_order_number}/{file.get('fileName', '')}"
                        })
            
            # Get all existing files
            existing_files = self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
            ).all()
            
            # Delete from MinIO only files that are NOT in keep list
            for file in existing_files:
                keep_this_file = False
                for keep_file in files_to_keep:
                    if keep_file["file_name"] == file.file_name:
                        keep_this_file = True
                        break
                
                if not keep_this_file:
                    # Delete from MinIO
                    try:
                        # Extract object name from URL
                        if file.file_url:
                            url_parts = file.file_url.split(f'/{self.bucket_name}/')
                            if len(url_parts) > 1:
                                object_name = url_parts[1]
                                self.minio_client.remove_object(self.bucket_name, object_name)
                                print(f"Deleted old file from MinIO: {object_name}")
                    except Exception as e:
                        print(f"Error deleting file from MinIO: {e}")
            
            # --- DELETE DATABASE RECORDS ---
            
            # Delete work_order_files
            self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            # Delete other related records
            self.db.query(SupportingDocuments).filter(
                SupportingDocuments.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            self.db.query(WorkOrderItems).filter(
                WorkOrderItems.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            self.db.query(WorkOrderVendors).filter(
                WorkOrderVendors.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            self.db.query(Authorizations).filter(
                Authorizations.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            self.db.flush()
            
            # --- RE-CREATE ALL DATA ---
            
            # Process attachments (will upload new files, skip existing ones)
            self._process_attachments_with_existing_files(
                request_data, work_orders_id, work_order_number, files_to_keep
            )
            
            # Create work items
            work_items_data = request_data.extract_work_items_data()
            for item_data in work_items_data:
                item_data['work_order_id'] = work_orders_id
                item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
                work_item = WorkOrderItems(**item_data)
                self.db.add(work_item)
            
            # Create vendors
            vendors_data = request_data.extract_vendor_data()
            for vendor_data in vendors_data:
                vendor_data['work_order_id'] = work_orders_id
                work_vendor = WorkOrderVendors(**vendor_data)
                self.db.add(work_vendor)
            
            # Create authorizations
            authorizations_data = request_data.extract_authorizations_data()
            for auth_data in authorizations_data:
                auth_data['work_order_id'] = work_orders_id
                authorization = Authorizations(**auth_data)
                self.db.add(authorization)
            
            # Commit
            self.db.commit()
            self.db.refresh(existing_work_order)
            
            return {
                "work_order": existing_work_order,
                "work_items_count": len(work_items_data),
                "total_cost": request_data.totalCost
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error updating work order: {str(e)}")
            raise Exception(f"Failed to update work order: {str(e)}")

    def _process_attachments_with_existing_files(self, request_data: WorkOrdersCreateRequest, work_order_id: int, work_order_number: str, files_to_keep: List[dict]):
        """Process attachments, preserving existing files and uploading new ones"""
        try:
            print("\n" + "=" * 80)
            print("STARTING FILE PROCESSING")
            print("=" * 80)
            
            attachments = json.loads(request_data.attachments)
            print(f"Work Order ID: {work_order_id}")
            print(f"Work Order Number: {work_order_number}")
            
            # Show full attachments structure for debugging
            print("\nFull attachments structure received:")
            print(json.dumps(attachments, indent=2))
            
            attachment_type_mapping = {
                'layout': 'layout',
                'documentation': 'documentation',
                'photoImages': 'photo_images',
                'billOfQuantity': 'bill_of_quantity'
            }
            
            total_new_files = 0
            total_existing_files = 0
            
            # Process each attachment type
            for field_name, section_data in attachments.items():
                print(f"\n{'='*40}")
                print(f"Processing: {field_name}")
                print(f"Section data: {json.dumps(section_data, indent=2)}")
                
                if isinstance(section_data, dict):
                    document_type = attachment_type_mapping.get(field_name, field_name)
                    uploaded = section_data.get('uploaded', False)
                    
                    if not uploaded:
                        print(f"Skipping {field_name} - not uploaded")
                        continue
                    
                    # Create supporting document
                    supporting_doc = SupportingDocuments(
                        work_order_id=work_order_id,
                        document_type=document_type,
                        has_document=uploaded
                    )
                    self.db.add(supporting_doc)
                    self.db.flush()
                    print(f"Created supporting document ID: {supporting_doc.id}")
                    
                    # Process files
                    if 'files' in section_data:
                        files = section_data['files']
                        if isinstance(files, list):
                            print(f"Found {len(files)} file(s) to process")
                            
                            for i, file_item in enumerate(files):
                                print(f"\n  Processing file {i+1}:")
                                print(f"    Raw item: {file_item}")
                                
                                if isinstance(file_item, dict):
                                    # Extract all possible keys for debugging
                                    all_keys = list(file_item.keys())
                                    print(f"    Keys found: {all_keys}")
                                    
                                    # Get filename from any possible key
                                    file_name = None
                                    for key in ['filename', 'fileName', 'Filename']:
                                        if key in file_item:
                                            file_name = file_item[key]
                                            print(f"    Found filename in key '{key}': {file_name}")
                                            break
                                    
                                    # Get file content from any possible key
                                    file_content = None
                                    for key in ['filecontent', 'fileContent', 'content', 'filecontent_hex']:
                                        if key in file_item:
                                            file_content = file_item[key]
                                            print(f"    Found content in key '{key}', length: {len(file_content)}")
                                            break
                                    
                                    # Get action
                                    action = file_item.get('action', 'new')
                                    print(f"    Action: {action}")
                                    
                                    if not file_name:
                                        print(f"    ERROR: No filename found!")
                                        continue
                                    
                                    if action == 'existing':
                                        # Handle existing file
                                        print(f"    Handling as existing file")
                                        file_url = f"http://10.10.1.7:9000/{self.bucket_name}/{work_order_number}/{file_name}"
                                        
                                        work_order_file = WorkOrderFiles(
                                            work_order_id=work_order_id,
                                            supporting_document_id=supporting_doc.id,
                                            file_name=file_name,
                                            file_url=file_url,
                                            file_size=0
                                        )
                                        self.db.add(work_order_file)
                                        total_existing_files += 1
                                        print(f"    ✓ Added existing file to database: {file_name}")
                                        
                                    elif file_content and len(file_content) > 10:
                                        # Handle new file with content
                                        print(f"    Handling as NEW file with content")
                                        try:
                                            print(f"    Attempting upload to MinIO...")
                                            file_url, file_size = self._upload_to_minio(
                                                work_order_number,
                                                file_name,
                                                file_content
                                            )
                                            
                                            work_order_file = WorkOrderFiles(
                                                work_order_id=work_order_id,
                                                supporting_document_id=supporting_doc.id,
                                                file_name=file_name,
                                                file_url=file_url,
                                                file_size=file_size
                                            )
                                            self.db.add(work_order_file)
                                            total_new_files += 1
                                            print(f"    ✓ UPLOADED NEW FILE: {file_name}")
                                            print(f"    ✓ URL: {file_url}")
                                            print(f"    ✓ Size: {file_size} bytes")
                                            
                                        except Exception as e:
                                            print(f"    ✗ FAILED to upload {file_name}: {e}")
                                            import traceback
                                            traceback.print_exc()
                                    else:
                                        print(f"    WARNING: File has no content or content too short: {file_name}")
                                        print(f"    Content length: {len(file_content) if file_content else 0}")
                                else:
                                    print(f"    WARNING: File item is not a dict: {type(file_item)}")
                        else:
                            # Handle new file with content
                            print(f"    Handling as NEW file with content")
                            try:
                                print(f"    Attempting upload to MinIO...")
                                file_url, file_size = self._upload_to_minio(
                                    work_order_number,
                                    file_name,
                                    file_content
                                )
                                
                                work_order_file = WorkOrderFiles(
                                    work_order_id=work_order_id,
                                    supporting_document_id=supporting_doc.id,
                                    file_name=file_name,
                                    file_url=file_url,
                                    file_size=file_size
                                )
                                self.db.add(work_order_file)
                                total_new_files += 1
                                print(f"    ✓ UPLOADED NEW FILE: {file_name}")
                                print(f"    ✓ URL: {file_url}")
                                print(f"    ✓ Size: {file_size} bytes")
                                
                            except Exception as e:
                                print(f"    ✗ FAILED to upload {file_name}: {e}")
                                import traceback
                                traceback.print_exc()
                    else:
                        print(f"No files in this section")
                else:
                    print(f"ERROR: Section data is not a dict: {type(section_data)}")
            
            print("\n" + "=" * 80)
            print(f"PROCESSING COMPLETE")
            print(f"Total existing files restored: {total_existing_files}")
            print(f"Total new files uploaded: {total_new_files}")
            print("=" * 80)
            
            # Commit to ensure files are saved
            self.db.flush()
            
        except Exception as e:
            print(f"\n✗ CRITICAL ERROR in file processing: {e}")
            import traceback
            traceback.print_exc()
            raise