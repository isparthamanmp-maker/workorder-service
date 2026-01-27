# src/services/work_orders_service.py
from typing import List, Optional, Dict, Any
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
    
    def _upload_to_minio(self, file_name: str, hex_content: str) -> str:
        """
        Upload file to MinIO and return the object URL
        
        Args:
            file_name: Name of the file
            hex_content: Hex string content of the file
        
        Returns:
            URL of the uploaded file
        """
        try:
            # Clean hex content (remove spaces and newlines)
            hex_content = hex_content.replace(" ", "").replace("\n", "").replace("\r", "")
            
            # Convert hex string to bytes
            file_bytes = binascii.unhexlify(hex_content)
            
            # Convert to file-like object
            file_data = io.BytesIO(file_bytes)
            file_size = len(file_bytes)
            
            # Create safe filename and object name
            safe_file_name = file_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            object_name = f"{datetime.now().strftime('%Y/%m/%d')}/{safe_file_name}"
            
            # Upload to MinIO
            self.minio_client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=self._get_content_type(file_name)
            )
            
            # Generate URL
            url = f"http://10.10.1.7:9000/{self.bucket_name}/{object_name}"
            return url, file_size
            
        except binascii.Error as e:
            print(f"Error decoding hex content for {file_name}: {e}")
            raise Exception(f"Invalid hex content in file {file_name}: {str(e)}")
        except Exception as e:
            print(f"Error uploading {file_name} to MinIO: {e}")
            raise Exception(f"Failed to upload file {file_name}: {str(e)}")
    
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
            
            # Process attachments and files
            self._process_attachments_and_files(request_data, work_order.id)

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
    
    def _process_attachments_and_files(self, request_data: WorkOrdersCreateRequest, work_order_id: int):
        """Process attachments and upload files to MinIO"""
        try:
            attachments = json.loads(request_data.attachments)
            
            # Define mapping between form field names and attachment types
            attachment_type_mapping = {
                'layout': 'layout',
                'documentation': 'documentation',
                'photoImages': 'photo_images',
                'billOfQuantity': 'bill_of_quantity'
            }
            
            # Process each attachment type
            for field_name, section_data in attachments.items():
                if isinstance(section_data, dict) and section_data.get('uploaded', False) and 'files' in section_data:
                    document_type = attachment_type_mapping.get(field_name, field_name)
                    
                    # Create supporting document entry
                    supporting_doc = SupportingDocuments(
                        work_order_id=work_order_id,
                        document_type=document_type,
                        has_document=True
                    )
                    self.db.add(supporting_doc)
                    self.db.flush()
                    
                    # Process each file in this section
                    files = section_data['files']
                    if isinstance(files, list):
                        for i in range(0, len(files), 2):
                            if i < len(files):
                                # Get file info
                                file_info = files[i]
                                
                                if isinstance(file_info, dict) and 'filename' in file_info:
                                    file_name = file_info['filename']
                                    
                                    # Look for filecontent
                                    file_content = None
                                    
                                    # Check if filecontent is in the same dict
                                    if 'filecontent' in file_info:
                                        file_content = file_info['filecontent']
                                    
                                    # Check if there's a next item with filecontent
                                    elif i + 1 < len(files):
                                        next_item = files[i + 1]
                                        if isinstance(next_item, dict) and 'filecontent' in next_item:
                                            file_content = next_item['filecontent']
                                    
                                    if file_content and isinstance(file_content, str):
                                        try:
                                            # Upload to MinIO
                                            file_url, file_size = self._upload_to_minio(file_name, file_content)
                                            
                                            # Store file info in database
                                            work_order_file = WorkOrderFiles(
                                                work_order_id=work_order_id,
                                                supporting_document_id=supporting_doc.id,
                                                file_name=file_name,
                                                file_url=file_url,
                                                file_size=file_size
                                            )
                                            self.db.add(work_order_file)
                                            print(f"Uploaded {file_name} to MinIO: {file_url}")
                                            
                                        except Exception as e:
                                            print(f"Failed to upload {file_name}: {e}")
                                            continue
                    else:
                        print(f"Files for {field_name} is not a list: {type(files)}")
                elif section_data.get('uploaded', False):
                    # Create supporting document entry even if no files
                    document_type = attachment_type_mapping.get(field_name, field_name)
                    supporting_doc = SupportingDocuments(
                        work_order_id=work_order_id,
                        document_type=document_type,
                        has_document=False
                    )
                    self.db.add(supporting_doc)
            
        except json.JSONDecodeError as e:
            print(f"Error parsing attachments JSON: {e}")
            raise Exception(f"Invalid attachments JSON format: {str(e)}")
        except Exception as e:
            print(f"Error processing files: {e}")
            raise Exception(f"Failed to process files: {str(e)}")
    

    def _delete_files_from_minio(self, files: List[WorkOrderFiles]):
        """Delete files from MinIO storage"""
        for file in files:
            try:
                # Extract object name from URL
                # URL format: http://10.10.1.7:9000/workorder/{object_name}
                if file.file_url:
                    # Parse the URL to get the object name
                    url_parts = file.file_url.split(f'/{self.bucket_name}/')
                    if len(url_parts) > 1:
                        object_name = url_parts[1]
                        
                        # Delete from MinIO
                        self.minio_client.remove_object(
                            bucket_name=self.bucket_name,
                            object_name=object_name
                        )
                        print(f"Deleted file from MinIO: {object_name}")
                    else:
                        print(f"Could not parse object name from URL: {file.file_url}")
            except Exception as e:
                print(f"Error deleting file from MinIO (file_id={file.id}, url={file.file_url}): {e}")
                # Don't raise exception here, continue with other files
                # The database deletion will still happen
                
    def update_work_order_from_request(self, work_orders_id: int, request_data: WorkOrdersCreateRequest) -> Dict[str, Any]:
        """Update existing work order from the complex request payload"""
        
        # First, get the existing work order
        existing_work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        
        if not existing_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        
        try:
            # Extract work order data for update
            work_order_data = request_data.extract_work_order_data()
            
            # Update the existing work order
            for key, value in work_order_data.items():
                if hasattr(existing_work_order, key):
                    setattr(existing_work_order, key, value)
            
            # Update the updated_at timestamp
            existing_work_order.updated_at = datetime.utcnow()
            
            # --- DELETE EXISTING DATA AND FILES FROM MINIO ---
            
            # Get all existing files before deletion
            existing_files = self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
            ).all()
            
            # Delete files from MinIO
            self._delete_files_from_minio(existing_files)
            
            # 1. First delete work_order_files that reference supporting_documents
            # Find all supporting_document_ids for this work order
            supporting_docs = self.db.query(SupportingDocuments).filter(
                SupportingDocuments.work_order_id == work_orders_id
            ).all()
            
            supporting_doc_ids = [doc.id for doc in supporting_docs]
            
            if supporting_doc_ids:
                # Delete work_order_files that reference these supporting_documents
                self.db.query(WorkOrderFiles).filter(
                    WorkOrderFiles.supporting_document_id.in_(supporting_doc_ids)
                ).delete(synchronize_session=False)
            
            # 2. Now delete supporting_documents
            self.db.query(SupportingDocuments).filter(
                SupportingDocuments.work_order_id == work_orders_id
            ).delete(synchronize_session=False)
            
            # 3. Also delete any work_order_files that might not have supporting_document_id
            # (direct work_order_id references)
            self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
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
            
            # Process new attachments and files
            self._process_attachments_and_files(request_data, work_orders_id)
            
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