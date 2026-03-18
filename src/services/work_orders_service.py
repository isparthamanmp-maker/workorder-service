from typing import List, Optional, Dict, Any, Tuple  # Add Tuple here
from sqlalchemy.orm import Session
from src.models.base import WorkOrders, WorkOrderItems, WorkOrderVendors, SupportingDocuments, Authorizations, WorkOrderFiles, WorkOrderBudgets, WorkOrdersHistory
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
from sqlalchemy import extract, text

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import requests
from urllib.parse import urlparse
from PyPDF2 import PdfReader, PdfWriter
import img2pdf
from PIL import Image as PILImage
import tempfile

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
            # print(f"    First 100 chars: {file_content[:100]}...")
            
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
        """Create work order from the complex request payload - UPDATED to match PUT process"""
        try:
            # Extract work order data
            work_order_data = request_data.extract_work_order_data()
            
            # Create work order
            work_order = WorkOrders(**work_order_data)
            self.db.add(work_order)
            self.db.flush()  # Flush to get the ID without committing
            
            # Store work order number
            work_order_number = work_order.document_number
            work_order_id = work_order.id
            
            print(f"\n{'='*80}")
            print(f"CREATING WORK ORDER (POST)")
            print(f"Work Order ID: {work_order_id}")
            print(f"Work Order Number: {work_order_number}")
            print(f"{'='*80}\n")
            
            # Make budget API call for EACH budget entry
            for budget_entry in request_data.budgetEntries:
                if budget_entry.get('isSelected', False):
                    url = f'{os.getenv("BUDGET_SERVICE")}/api/v1/budget_final_realisasis/'
                    payload = json.dumps({
                        "budget_index": budget_entry.get('budgetIndex', work_order.budget_index),
                        "refid": work_order.id,
                        "refnum": work_order.document_number,
                        "refvalue": float(budget_entry.get('costEstimation') or 0),
                        "created_by": "Ketut Sakho Parthama"
                    })
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    
                    response = requests.request("POST", url, headers=headers, data=payload)
                    
                    # Check if API call was successful
                    if response.status_code not in [200, 201]:
                        print(f"Warning: Budget API call failed for {budget_entry.get('budgetIndex')}: {response.text}")
            
            # Process supporting documents and files
            self._process_supporting_documents_put_style(request_data, work_order_id, work_order_number)
            
            # Extract and create work items
            work_items_data = request_data.extract_work_items_data()
            for item_data in work_items_data:
                item_data['work_order_id'] = work_order_id
                item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
                work_item = WorkOrderItems(**item_data)
                self.db.add(work_item)
            
            # Extract and create vendor data
            vendors_data = request_data.extract_vendor_data()
            for vendor_data in vendors_data:
                vendor_data['work_order_id'] = work_order_id
                work_vendor = WorkOrderVendors(**vendor_data)
                self.db.add(work_vendor)
            
            # Extract and create budget entries data
            budget_entries_data = self.extract_budget_entries_data(request_data, work_order_id)
            for budget_data in budget_entries_data:
                budget_item = WorkOrderBudgets(**budget_data)
                self.db.add(budget_item)
            
            # Extract and create authorizations data
            authorizations_data = request_data.extract_authorizations_data()
            for auth_data in authorizations_data:
                auth_data['work_order_id'] = work_order_id
                authorization = Authorizations(**auth_data)
                self.db.add(authorization)
            
            # Commit transaction
            self.db.commit()
            self.db.refresh(work_order)
            
            # Prepare response
            response = {
                "work_order": work_order,
                "work_items_count": len(work_items_data),
                "budget_entries_count": len(budget_entries_data),
                "total_cost": request_data.totalCost
            }
            
            print(f"\n{'='*80}")
            print(f"WORK ORDER CREATED SUCCESSFULLY")
            print(f"Work Order: {work_order_number}")
            print(f"Total Items: {len(work_items_data)}")
            print(f"Budget Entries: {len(budget_entries_data)}")
            print(f"{'='*80}")
            
            return response
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creating work order: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to create work order: {str(e)}")
    
    def extract_budget_entries_data(self, request_data: WorkOrdersCreateRequest, work_order_id: int) -> List[Dict[str, Any]]:
        """Extract budget entries data for work_order_budgets table"""
        budget_entries = []
        
        for idx, entry in enumerate(request_data.budgetEntries):
            budget_entries.append({
                'work_order_id': work_order_id,
                'budget_index': entry.get('budgetIndex', ''),
                'budget_name': entry.get('budgetName', ''),
                'cost_estimation': float(entry.get('costEstimation') or 0),
                'budget_remaining': float(entry.get('budgetRemaining') or 0),
                'under_over': entry.get('underOver', ''),
                'entry_order': entry.get('entryOrder', idx + 1),
                'is_selected': bool(entry.get('isSelected', False))
            })
        
        return budget_entries
    def _process_supporting_documents_put_style(self, request_data: WorkOrdersCreateRequest, work_order_id: int, work_order_number: str):
        """Process supporting documents and upload files to MinIO - UPDATED to match PUT style"""
        try:
            print("\n" + "=" * 80)
            print("DEBUG: Processing supporting documents in PUT style (same as update)")
            print(f"Work Order ID: {work_order_id}")
            print(f"Work Order Number: {work_order_number}")
            
            # Use supportingDocuments from the schema
            supporting_docs = request_data.supportingDocuments
            print(f"\nDEBUG: Number of supporting documents: {len(supporting_docs)}")
            
            # Print structure for debugging
            print(f"\nDEBUG: Supporting documents structure:")
            # print(json.dumps(supporting_docs, indent=2))
            
            total_files_processed = 0
            
            # Process each supporting document
            for doc_idx, doc in enumerate(supporting_docs):
                print(f"\n{'='*40}")
                print(f"Processing document {doc_idx + 1}:")
                
                document_type = doc.get('documentType', '')
                has_document = doc.get('hasDocument', False)
                files = doc.get('files', [])
                
                print(f"Document Type: {document_type}")
                print(f"Has Document: {has_document}")
                print(f"Number of files: {len(files)}")
                
                if not has_document or len(files) == 0:
                    print(f"Skipping - no document or no files")
                    # Still create supporting document record
                    supporting_doc = SupportingDocuments(
                        work_order_id=work_order_id,
                        document_type=document_type,
                        has_document=False
                    )
                    self.db.add(supporting_doc)
                    continue
                
                # Create supporting document
                supporting_doc = SupportingDocuments(
                    work_order_id=work_order_id,
                    document_type=document_type,
                    has_document=True
                )
                self.db.add(supporting_doc)
                self.db.flush()
                print(f"Created supporting document: ID={supporting_doc.id}, Type={document_type}")
                
                # Process files
                for file_idx, file_item in enumerate(files):
                    print(f"\n  Processing file {file_idx + 1}:")
                    
                    if isinstance(file_item, dict):
                        # Look for filename and filecontent in various possible keys
                        file_name = None
                        file_content = None
                        
                        # Find filename
                        for key in ['fileName', 'filename', 'name']:
                            if key in file_item and file_item[key]:
                                file_name = file_item[key]
                                break
                        
                        # Find file content
                        for key in ['fileContent', 'filecontent', 'content', 'data']:
                            if key in file_item and file_item[key]:
                                file_content = file_item[key]
                                break
                        
                        # For POST, we expect new files with content
                        if file_name and file_content and len(file_content) > 10:
                            try:
                                # Upload to MinIO using work order number structure
                                file_url, file_size = self._upload_to_minio(
                                    work_order_number, 
                                    file_name, 
                                    file_content
                                )
                                
                                # Create WorkOrderFiles record
                                work_order_file = WorkOrderFiles(
                                    work_order_id=work_order_id,
                                    supporting_document_id=supporting_doc.id,
                                    file_name=file_name,
                                    file_url=file_url,
                                    file_size=file_size
                                )
                                self.db.add(work_order_file)
                                total_files_processed += 1
                                print(f"    ✓ Uploaded: {file_name}")
                            except Exception as e:
                                print(f"    ✗ Failed to upload {file_name}: {e}")
                        else:
                            print(f"    Skipping - missing filename or content")
                            print(f"    File name: {file_name}")
                            print(f"    Content available: {'Yes' if file_content and len(file_content) > 10 else 'No'}")
                    else:
                        print(f"    Skipping - not a dictionary: {type(file_item)}")
            
            print(f"\n{'='*80}")
            print(f"Supporting documents processing complete")
            print(f"Total files uploaded: {total_files_processed}")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n✗ ERROR in supporting documents processing: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    
    
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
                joinedload(WorkOrders.files),
                joinedload(WorkOrders.budget_entries)  # Add this line

            )
            .filter(WorkOrders.id == work_orders_id)
            .first()
        )
        
        if not work_order:
            return None

        # Get history
        history = (
            self.db.query(WorkOrdersHistory)
            .filter(WorkOrdersHistory.refid == work_orders_id)
            .order_by(WorkOrdersHistory.created_at.desc())
            .all()
        )
        
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
                "costEstimation": float(work_order.cost_estimation or 0),
                "remainingBudget": float(work_order.remaining_budget or 0),
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
                    "quantity": float(item.quantity or 0),
                    "unitPrice": float(item.unit_price or 0),
                    "totalPrice": float(item.total_price or 0),
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
            "budgetEntries": [  # Add this section
                {
                    "id": budget.id,
                    "workOrderId": budget.work_order_id,
                    "budgetIndex": budget.budget_index,
                    "budgetName": budget.budget_name,
                    "costEstimation": float(budget.cost_estimation or 0),
                    "budgetRemaining": float(budget.budget_remaining or 0),
                    "underOver": budget.under_over,
                    "entryOrder": budget.entry_order,
                    "isSelected": bool(budget.is_selected)
                }
                for budget in work_order.budget_entries
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
                            'uploadDate': file.upload_date.isoformat() if file.upload_date else None,
                            'remarks': file.remarks
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
                    'uploadDate': file.upload_date.isoformat() if file.upload_date else None,
                    'remarks': file.remarks
                }
                for file in work_order.files
            ],
            'authorizations': [self._format_authorizations_response(work_order.authorizations)],
            "totalCost": float(sum(
                (item.quantity or 0) * (item.unit_price or 0) 
                for item in work_order.work_items
            )),
            "history": [
                {
                    "id": h.id,
                    "userGroup": h.UserGroup,
                    "status": h.status,
                    "remarks": h.remarks,
                    "createdAt": h.created_at.isoformat() if h.created_at else None,
                    "createdBy": h.created_by
                }
                for h in history
            ],
            "latestRemark": next((h.remarks for h in history if h.remarks), None),
            "latestRemarkMetadata": next((
                {
                    "createdBy": h.created_by,
                    "createdAt": h.created_at.isoformat() if h.created_at else None
                } 
                for h in history if h.remarks
            ), None)
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
    
    def get_work_orderss(self, skip: int = 0, limit: int = 100, order_by: str = "id", user_group: Optional[str] = None, approve_all: bool = False) -> List[WorkOrders]:
        """Get work_orderss with pagination, ordering, and optional role-based filtering"""
        from sqlalchemy import func, and_, or_, exists
        
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
        
        query = self.db.query(WorkOrders)

        if user_group:
            # Handle Admin roles - see everything
            if user_group in ["Admin", "Administrator"]:
                return query.order_by(order_column).offset(skip).limit(limit).all()

            # Identify if it's a known approver group (matching the actual DB ENUM values)
            auth_type = None
            # Map: user group → their authorization step in the DB
            GROUP_AUTH_TYPE = {
                "ACC": "verified_by_acc_dept",
                "BM": "approved_by_bm",
                "GM": "approved_by_bm",    # GM = General Manager = Business Manager step
                "DIR": "approved_by_director",
                "PUR": "received_by_purchasing",
            }
            # Prerequisite: which step must be done BEFORE showing to this group
            PREREQUISITE_AUTH_TYPE = {
                "ACC": "dept_head",
                "BM": "verified_by_acc_dept",
                "GM": "verified_by_acc_dept",
                "DIR": "approved_by_bm",
                "PUR": "approved_by_director",
            }
            auth_type = GROUP_AUTH_TYPE.get(user_group)
            prerequisite_auth_type = PREREQUISITE_AUTH_TYPE.get(user_group, "dept_head")

            # Subquery for next pending authorization (minimal ID with authorization_date is NULL)
            pending_auth_sub = self.db.query(func.min(Authorizations.id)).filter(
                Authorizations.authorization_date == None,
                Authorizations.work_order_id == WorkOrders.id
            ).scalar_subquery()

            # Filter logic:
            # 1. Always see items submitted by your department/group
            # 2. IF approve_all is TRUE AND you are a global approver (ACC, BM, etc.):
            #    ALSO see items from ANY department IF it's your turn to approve
            # 3. ELSE (regular user OR no approve_all):
            #    ALSO see items from your department IF it's currently pending dept_head approval
            
            filter_conditions = [WorkOrders.submitted_by == user_group]

            if approve_all and auth_type:
                # Add condition: Actionable for my specific global role (any department)
                # AND the prerequisite step must have already been approved
                prerequisite_approved_sub = exists().where(
                    and_(
                        Authorizations.work_order_id == WorkOrders.id,
                        Authorizations.authorization_type == prerequisite_auth_type,
                        Authorizations.authorization_date != None
                    )
                )
                filter_conditions.append(
                    and_(
                        prerequisite_approved_sub,
                        exists().where(
                            and_(
                                Authorizations.work_order_id == WorkOrders.id,
                                Authorizations.authorization_type == auth_type,
                                Authorizations.authorization_date == None,
                                Authorizations.id == pending_auth_sub
                            )
                        )
                    )
                )
            else:
                # Add condition: Pending dept_head approval for my own department
                filter_conditions.append(
                    exists().where(
                        and_(
                            Authorizations.work_order_id == WorkOrders.id,
                            Authorizations.authorization_type == 'dept_head',
                            Authorizations.authorization_date == None,
                            Authorizations.id == pending_auth_sub,
                            WorkOrders.submitted_by == user_group
                        )
                    )
                )
            
            query = query.filter(or_(*filter_conditions))
        
        work_orders = query.order_by(order_column)\
            .offset(skip)\
            .limit(limit)\
            .all()

        # Enrich each work order with the last approver name
        wo_ids = [wo.id for wo in work_orders]
        if wo_ids:
            # Get the max-ID authorization with a date for each work order (= last approved step)
            last_auth_subq = (
                self.db.query(
                    Authorizations.work_order_id,
                    func.max(Authorizations.id).label("max_id")
                )
                .filter(
                    Authorizations.work_order_id.in_(wo_ids),
                    Authorizations.authorization_date != None
                )
                .group_by(Authorizations.work_order_id)
                .subquery()
            )
            last_auths = (
                self.db.query(Authorizations)
                .join(last_auth_subq, and_(
                    Authorizations.work_order_id == last_auth_subq.c.work_order_id,
                    Authorizations.id == last_auth_subq.c.max_id
                ))
                .all()
            )
            # Build a map from work_order_id → last approver name
            last_approver_map = {a.work_order_id: a.person_name for a in last_auths}
            for wo in work_orders:
                wo.last_approver = last_approver_map.get(wo.id) or None

        return work_orders
    
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
        Generate the next document number in format:
        {number}/WOR/{submitted_by}/NMP/{ROMAN_MONTH}/{YYYY}

        Example:
        0009/WOR/IT_Dept/NMP/II/2025
        """

        # Roman numeral map for months
        MONTH_TO_ROMAN = {
            1: "I", 2: "II", 3: "III", 4: "IV",
            5: "V", 6: "VI", 7: "VII", 8: "VIII",
            9: "IX", 10: "X", 11: "XI", 12: "XII"
        }

        now = datetime.now()
        current_year = now.year
        roman_month = MONTH_TO_ROMAN[now.month]

        # Query highest document number for this submitted_by & year
        query = self.db.query(WorkOrders.document_number).filter(
            WorkOrders.submitted_by == submitted_by,
            extract('year', WorkOrders.request_date) == current_year
        ).all()

        max_number = 0

        for doc_num_row in query:
            doc_num = doc_num_row[0]
            if doc_num:
                # Expected format: 0009/WOR/IT_Dept/NMP/II/2025
                parts = doc_num.split('/')
                if parts and parts[0].isdigit():
                    number_part = int(parts[0])
                    max_number = max(max_number, number_part)

        next_number = max_number + 1
        number_str = f"{next_number:04d}"

        # Final document number
        new_document_number = (
            f"{number_str}/WOR/{submitted_by}/NMP/{roman_month}/{current_year}"
        )

        return new_document_number


    def update_work_order_with_existing_files(self, work_orders_id: int, request_data: WorkOrdersCreateRequest, original_supporting_docs: List[dict]) -> Dict[str, Any]:
        """Update work order but preserve existing files marked as 'existing'"""
        # Debug: Print the entire request_data
        print(f"Request data type: {type(request_data)}")
        print(f"Request data dict: {request_data.dict() if hasattr(request_data, 'dict') else request_data}")
        
        # Get existing work order
        existing_work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        print(f"Existing doc number: {existing_work_order.document_number}")
        
        # Get existing work order
        existing_work_order = self.db.query(WorkOrders).filter(WorkOrders.id == work_orders_id).first()
        
        if not existing_work_order:
            raise HTTPException(status_code=404, detail="Work order not found")
        
        try:
           # Store work order number
            work_order_number = existing_work_order.document_number

            # Extract work order data for update
            work_order_data = request_data.extract_work_order_data()
            
            # Update work order fields
            for key, value in work_order_data.items():
                print(key, value)
                if hasattr(existing_work_order, key):
                    setattr(existing_work_order, key, value)

            print("request_data:",request_data)

            existing_work_order.remaining_budget = request_data.workOrder['budgetRemaining']
            existing_work_order.under_over = request_data.workOrder['under_over']
            existing_work_order.recommended_contractor = request_data.workOrder['recommended_contractor']
            existing_work_order.reason = request_data.workOrder['reason']
            
            existing_work_order.document_number=work_order_number

            print("existing_work_order:",existing_work_order)
            
            print(f"Existing doc number After loop: {existing_work_order.document_number}")

            existing_work_order.updated_at = datetime.utcnow()
            
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
            
            # Delete work_order_file_comments first due to foreign key constraint
            self.db.execute(
                text("DELETE FROM work_order_file_comments WHERE work_order_file_id IN (SELECT id FROM work_order_files WHERE work_order_id = :wo_id)"),
                {"wo_id": work_orders_id}
            )

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
            
            self.db.query(WorkOrderBudgets).filter(
                WorkOrderBudgets.work_order_id == work_orders_id
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
            
            # Create budget entries
            budget_entries_data = self.extract_budget_entries_data(request_data, work_orders_id)  # Add this
            for budget_data in budget_entries_data:
                budget_item = WorkOrderBudgets(**budget_data)
                self.db.add(budget_item)
                
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
            
            # FIX: Use supportingDocuments directly since it's already a list
            attachments = request_data.supportingDocuments  # Remove json.loads()
            
            print(f"Work Order ID: {work_order_id}")
            print(f"Work Order Number: {work_order_number}")
            
            # Show full attachments structure for debugging
            print("\nFull attachments structure received:")
            # print(json.dumps(attachments, indent=2))
            
            # Instead of the old field mapping, use the new structure directly
            total_new_files = 0
            total_existing_files = 0
            
            # Process each supporting document
            for doc_idx, doc in enumerate(attachments):
                print(f"\n{'='*40}")
                print(f"Processing document {doc_idx + 1}:")
                
                document_type = doc.get('documentType', '')
                has_document = doc.get('hasDocument', False)
                files = doc.get('files', [])
                
                print(f"Document Type: {document_type}")
                print(f"Has Document: {has_document}")
                print(f"Number of files: {len(files)}")
                
                if not has_document or len(files) == 0:
                    print(f"Skipping - no document or no files")
                    # Still create supporting document record
                    supporting_doc = SupportingDocuments(
                        work_order_id=work_order_id,
                        document_type=document_type,
                        has_document=False
                    )
                    self.db.add(supporting_doc)
                    continue
                
                # Create supporting document
                supporting_doc = SupportingDocuments(
                    work_order_id=work_order_id,
                    document_type=document_type,
                    has_document=True
                )
                self.db.add(supporting_doc)
                self.db.flush()
                print(f"Created supporting document: ID={supporting_doc.id}, Type={document_type}")
                
                # Process files
                for file_idx, file_item in enumerate(files):
                    print(f"\n  Processing file {file_idx + 1}:")
                    print(f"    Raw item: {file_item}")
                    
                    if isinstance(file_item, dict):
                        # Extract all possible keys for debugging
                        all_keys = list(file_item.keys())
                        print(f"    Keys found: {all_keys}")
                        
                        # Get filename from any possible key
                        file_name = None
                        for key in ['fileName', 'filename', 'name']:
                            if key in file_item:
                                file_name = file_item[key]
                                print(f"    Found filename in key '{key}': {file_name}")
                                break
                        
                        # Get file content from any possible key
                        file_content = None
                        for key in ['fileContent', 'filecontent', 'content']:
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
                                file_size=0  # Size unknown for existing files
                            )
                            self.db.add(work_order_file)
                            total_existing_files += 1
                            print(f"    ✓ Added existing file to database: {file_name}")
                            
                        elif action in ['new', 'add']:
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
                            print(f"    WARNING: Unknown action '{action}', treating as existing")
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
                    else:
                        print(f"    WARNING: File item is not a dict: {type(file_item)}")
            
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

    # src/services/work_orders_service.py
    # Update the generate_work_order_pdf method with these changes

    def generate_work_order_pdf(self, work_order_data: dict) -> io.BytesIO:
        """Generate PDF from work order data"""
        buffer = io.BytesIO()
        
        # Create the PDF document
        pdf_doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        # Calculate page width for full-width tables (subtract left and right margins)
        page_width = A4[0] - 40  # 595.27 - 40 = 555.27 points for A4
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'HeadingStyle',
            parent=styles['Heading2'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceBefore=6,
            spaceAfter=4
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            spaceAfter=2
        )
        
        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.black
        )
        
        # Story builder (list of elements)
        story = []
        
        # Extract data
        work_order = work_order_data['workOrder']
        work_items = work_order_data['workItems']
        tender_vendors = work_order_data['tenderVendorData']
        budget_entries = work_order_data.get('budgetEntries', [])
        supporting_docs = work_order_data.get('supportingDocuments', [])
        authorizations_list = work_order_data.get('authorizations', [{}])
        
        # Format currency function
        def format_currency(amount):
            if amount is None:
                return "Rp 0"
            try:
                return f"Rp {float(amount):,.0f}".replace(',', '.')
            except (ValueError, TypeError):
                return f"Rp {amount}" if amount else "Rp 0"
        
        # 1. Header
        story.append(Paragraph("PT. Nusa Mandiri Properti", normal_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph("WORK ORDER REQUEST FORM", title_style))
        story.append(Spacer(1, 8))
        
        # 2. Basic Information - Fixed column widths

        # Calculate column widths for full-width layout
        # Left side: Request Type and To (40% of page width)
        # Right side: Date and WOR No (60% of page width)
        left_width = page_width * 0.4
        right_width = page_width * 0.6

        # Create left table
        left_data = [
            ["Request Type:", "Item Request" if work_order.get('requestType') == 'item_request' else "Work Order Request"],
            ["To:", "Acc & Purchasing Department"]
        ]

        left_table = Table(left_data, colWidths=[left_width * 0.3, left_width * 0.7])
        left_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            # All columns left-aligned
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            # Consistent padding - NO BORDERS
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            # NO GRID, NO BOX, NO BORDERS
            # Removed all border/line styling
        ]))

        # Create right table
        right_data = [
            ["Date:", work_order.get('requestDate', 'N/A')],
            ["WOR No:", work_order.get('documentNumber', 'N/A')]
        ]

        right_table = Table(right_data, colWidths=[right_width * 0.2, right_width * 0.8])
        right_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            # All columns left-aligned
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            # Consistent padding - NO BORDERS
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            # NO GRID, NO BOX, NO BORDERS
            # Removed all border/line styling
        ]))

        # Combine tables side by side to span full width
        basic_info_table = Table([[left_table, right_table]], colWidths=[left_width, right_width])
        basic_info_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(basic_info_table)
        story.append(Spacer(1, 8))
        
        # 3. Request Submitted By
        story.append(Paragraph(f"1. Request is submitted by: {work_order.get('submittedBy', 'N/A')}", heading_style))
        story.append(Spacer(1, 4))
        
        # 4. Schedule of Works - Full width
        schedule_text = f"2. Schedule of Works: Start Date: {work_order.get('startDate', 'N/A')}  End Date: {work_order.get('endDate', 'N/A')}"
        if work_order.get('isUrgent'):
            schedule_text += "  [URGENT]"
        story.append(Paragraph(schedule_text, heading_style))
        story.append(Spacer(1, 4))
        
        # 5. Scope of Works
        story.append(Paragraph("3. Scope of Works", heading_style))
        story.append(Spacer(1, 2))

        # Scope description - Full width bordered box with text wrapping
        scope_text = work_order.get('scopeOfWorks', 'N/A')

        # Use Paragraph for automatic text wrapping
        scope_para = Paragraph(scope_text, normal_style)
        scope_data = [[scope_para]]
        scope_table = Table(scope_data, colWidths=[page_width])
        scope_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),  # Changed to TOP for better wrapping
            ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(scope_table)
        story.append(Spacer(1, 8))

        # Work Items Table - Full width with wrapped description
        story.append(Paragraph("Description:", normal_style))
        story.append(Spacer(1, 2))

        if work_items:
            # Prepare table data with Paragraph for description to enable wrapping
            table_data = [['Description', 'Qty', 'Unit Price', 'Total']]
            
            for item in work_items:
                quantity = float(item.get('quantity') or 0)
                unit_price = float(item.get('unitPrice') or 0)
                total_price = float(item.get('totalPrice') or (quantity * unit_price))
                
                # Wrap description in Paragraph for text wrapping
                desc_text = item.get('description', '')
                desc_para = Paragraph(desc_text, normal_style)
                
                table_data.append([
                    desc_para,  # Use Paragraph instead of plain text
                    str(int(quantity)) if quantity == int(quantity) else str(quantity),
                    format_currency(unit_price),
                    format_currency(total_price)
                ])
            
            # Create table with full width columns
            # Make description column wider to accommodate wrapped text
            col_widths = [page_width - 240, 60, 90, 90]  # Description takes remaining width
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ALIGN', (1,0), (1,-1), 'CENTER'),
                ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),  # Changed to TOP for wrapped text
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('WORDWRAP', (0,1), (0,-1), True),  # Enable word wrap for description column
            ]))
            story.append(table)
        else:
            story.append(Paragraph("No work items specified", normal_style))
        
        story.append(Spacer(1, 8))
        
        # 6. Attachments / Supporting Documents
        story.append(Paragraph("Attachment / Supporting Document:", heading_style))
        story.append(Spacer(1, 2))
        
        # Group files by document type
        if supporting_docs:
            for doc in supporting_docs:
                doc_type = doc.get('documentType', '')
                files = doc.get('files', [])
                doc_label = doc_type.replace('_', ' ').title()
                check = "☑" if doc.get('hasDocument', False) and len(files) > 0 else "☐"
                file_count = f" ({len(files)} files)" if files else ""
                story.append(Paragraph(f"{check} {doc_label}{file_count}", normal_style))
        else:
            story.append(Paragraph("No attachments specified", normal_style))
        
        story.append(Spacer(1, 8))
        
        # 7. Type of Cost
        story.append(Paragraph("4. TYPE OF COST", heading_style))
        story.append(Spacer(1, 2))
        
        # Budget Status
        is_budgeted = work_order.get('budgetStatus') == 'budgeted'
        budget_status = "BUDGETED" if is_budgeted else "UNBUDGETED"
        story.append(Paragraph(f"Budget Status: {budget_status}", normal_style))
        
        # Cost Type
        cost_type = work_order.get('costType', 'CAPEX')
        story.append(Paragraph(f"Cost Type: {cost_type}", normal_style))
        story.append(Spacer(1, 4))
        
        # Budget Allocation Table - FULL WIDTH with consistent margins
        # 7. Type of Cost - Budget Allocation Table with wrapped Budget Name
        if budget_entries:
            story.append(Paragraph("Budget Allocation:", normal_style))
            story.append(Spacer(1, 2))
            
            # Filter only selected budget entries
            selected_budgets = [b for b in budget_entries if b.get('isSelected', False)]
            
            if selected_budgets:
                # Prepare table data with Paragraph for Budget Name to enable wrapping
                table_data = [['No.', 'Budget Index', 'Budget Name', 'Cost Estimation', 'Remaining', 'Under/Over']]
                
                total_cost_est = 0
                total_remaining = 0
                total_under_over = 0
                
                for idx, entry in enumerate(selected_budgets, 1):
                    cost_est = float(entry.get('costEstimation') or 0)
                    remaining = float(entry.get('budgetRemaining') or 0)
                    try:
                        under_over = float(entry.get('underOver') or 0)
                    except (ValueError, TypeError):
                        under_over = 0
                    
                    total_cost_est += cost_est
                    total_remaining += remaining
                    total_under_over += under_over
                    
                    # Wrap Budget Name in Paragraph for text wrapping
                    budget_name_text = entry.get('budgetName', '')
                    budget_name_para = Paragraph(budget_name_text, normal_style)
                    
                    table_data.append([
                        str(idx),
                        entry.get('budgetIndex', ''),
                        budget_name_para,  # Use Paragraph instead of plain text
                        format_currency(cost_est),
                        format_currency(remaining),
                        format_currency(under_over)
                    ])
                
                # Add total row
                table_data.append([
                    '', '', 'Total:',
                    format_currency(total_cost_est),
                    format_currency(total_remaining),
                    format_currency(total_under_over)
                ])
                
                # Calculate full width columns for budget table
                # Make Budget Name column wider to accommodate wrapped text
                col_widths = [30, 110, 160, 100, 100, 100]
                # Adjust to fit page width
                total_width = sum(col_widths)
                scale_factor = page_width / total_width
                col_widths = [w * scale_factor for w in col_widths]
                
                table = Table(table_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTNAME', (0,1), (-1,-2), 'Helvetica'),
                    ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('ALIGN', (0,0), (0,-1), 'CENTER'),
                    ('ALIGN', (1,0), (1,-1), 'LEFT'),
                    ('ALIGN', (2,0), (2,-1), 'LEFT'),  # Budget Name left-aligned
                    ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),  # Changed to TOP for wrapped text
                    ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
                    ('GRID', (0,-1), (-1,-1), 0.5, colors.grey),
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                    ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('LEFTPADDING', (0,0), (-1,-1), 4),
                    ('RIGHTPADDING', (0,0), (-1,-1), 4),
                    ('WORDWRAP', (2,1), (2,-2), True),  # Enable word wrap for Budget Name column
                ]))
                story.append(table)
            else:
                story.append(Paragraph("No budget entries selected", normal_style))
        else:
            story.append(Paragraph("No budget entries specified", normal_style))
        
        story.append(Spacer(1, 4))
        
        # Charge to Tenant
        charge_to_tenant = work_order.get('chargeToTenant', False)
        charge_text = "YES (forward to billing request)" if charge_to_tenant else "NO"
        story.append(Paragraph(f"Charge to Tenant / Vendor: {charge_text}", normal_style))
        story.append(Spacer(1, 8))
        
        # 8. Vendor / Contractor
        story.append(Paragraph("5. VENDOR / CONTRACTOR", heading_style))
        story.append(Spacer(1, 2))
        
        # Recommended Contractor
        vendor_name = work_order.get('recommendedContractor', 'N/A')
        vendor_reason = work_order.get('reason', 'N/A')
        story.append(Paragraph(f"Recommended Contractor: {vendor_name}", normal_style))
        story.append(Paragraph(f"Reason: {vendor_reason}", normal_style))
        story.append(Spacer(1, 2))
        
        # Vendor Selection Method
        vendor_method = work_order.get('vendorSelectionMethod', 'sole_source_vendor')
        method_text = "tender process" if 'tender' in str(vendor_method) else "sole source vendor"
        story.append(Paragraph(f"Vendor Selection Method: {method_text}", normal_style))
        story.append(Spacer(1, 2))
        
        # Tender Vendor Comparison - FULL WIDTH
        if tender_vendors and len(tender_vendors) > 0:
            story.append(Paragraph("Tender Vendor Comparison:", normal_style))
            story.append(Spacer(1, 2))
            
            # Prepare table data - show only first 3
            table_data = [['No.', 'Name of Vendor']]
            for idx, vendor in enumerate(tender_vendors[:3], 1):
                table_data.append([str(idx), vendor.get('vendorName', '')])
            
            # Full width columns for vendor table
            col_widths = [30, page_width - 50]  # No. column small, Name takes rest
            
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ALIGN', (0,0), (0,-1), 'CENTER'),
                ('ALIGN', (1,0), (1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(table)
        
        story.append(Spacer(1, 8))
        
        # 9. Authorization - FULL WIDTH
        story.append(Paragraph("6. AUTHORIZATION", heading_style))
        story.append(Spacer(1, 4))
        
        # Create authorization section
        auth_data = authorizations_list[0] if authorizations_list else {}
        
        # Authorization boxes
        auth_boxes = [
            ("Prepared By:", auth_data.get('preparedBy', '')),
            ("Approved By Dep. Head:", auth_data.get('deptHeadName', '')),
            ("Verified by Acc. Dept.:", auth_data.get('accDeptName', '')),
            ("Approved by BM:", auth_data.get('bmName', '')),
            ("Approved by Director:", auth_data.get('directorName', '')),
            ("Received by Purchasing:", auth_data.get('purchasingName', ''))
        ]
        
        # Get dates
        auth_dates = {
            "Prepared By:": auth_data.get('preparedDate', ''),
            "Approved By Dep. Head:": auth_data.get('deptHeadDate', ''),
            "Verified by Acc. Dept.:": auth_data.get('accDeptDate', ''),
            "Approved by BM:": auth_data.get('bmDate', ''),
            "Approved by Director:": auth_data.get('directorDate', ''),
            "Received by Purchasing:": auth_data.get('purchasingDate', '')
        }
        
        # Create table for auth boxes - full width with equal columns
        auth_table_data = []
        row_data = []
        for i, (label, value) in enumerate(auth_boxes):
            date_value = auth_dates.get(label, '')
            date_text = f"Date: {date_value}" if date_value else "Date: "
            box_content = f"{label}\n\n{value}\n\n{date_text}"
            row_data.append(box_content)
            if (i + 1) % 3 == 0 or i == len(auth_boxes) - 1:
                while len(row_data) < 3:
                    row_data.append('')
                auth_table_data.append(row_data)
                row_data = []
        
        # Full width columns for auth boxes
        auth_col_width = page_width / 3
        
        table = Table(auth_table_data, colWidths=[auth_col_width, auth_col_width, auth_col_width])
        table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(table)
        story.append(Spacer(1, 8))
        
        # 10. Footer
        story.append(Spacer(1, 20))
        story.append(Paragraph("NMP-F27 rev00-20240826", 
                            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))
        
        # Build PDF
        pdf_doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    def get_supporting_files(self, work_orders_id: int) -> List[dict]:
        """Get all supporting files for a work order"""
        try:
            # Query all files for this work order
            files = self.db.query(WorkOrderFiles).filter(
                WorkOrderFiles.work_order_id == work_orders_id
            ).all()
            
            file_list = []
            for file in files:
                file_list.append({
                    'id': file.id,
                    'file_name': file.file_name,
                    'file_url': file.file_url,
                    'file_size': file.file_size
                })
            
            return file_list
            
        except Exception as e:
            print(f"Error getting supporting files: {e}")
            return []
    
    def download_file_from_minio(self, file_url: str) -> Optional[bytes]:
        """Download file from MinIO"""
        try:
            # Extract object path from URL
            parsed_url = urlparse(file_url)
            path_parts = parsed_url.path.split(f'/{self.bucket_name}/')
            
            if len(path_parts) > 1:
                object_path = path_parts[1]
                
                # Get file from MinIO
                response = self.minio_client.get_object(self.bucket_name, object_path)
                file_data = response.read()
                response.close()
                response.release_conn()
                
                return file_data
            else:
                print(f"Could not extract object path from URL: {file_url}")
                return None
                
        except Exception as e:
            print(f"Error downloading file from MinIO: {e}")
            return None
    
    def convert_to_pdf(self, file_data: bytes, file_name: str) -> Optional[io.BytesIO]:
        """Convert file to PDF format"""
        try:
            file_ext = os.path.splitext(file_name)[1].lower()
            
            # If already PDF, return as is
            if file_ext == '.pdf':
                return io.BytesIO(file_data)
            
            # Convert images to PDF
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                # Use PIL to open image
                image = PILImage.open(io.BytesIO(file_data))
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Create PDF
                pdf_buffer = io.BytesIO()
                image.save(pdf_buffer, format='PDF')
                pdf_buffer.seek(0)
                return pdf_buffer
            
            # For other file types, create a cover page
            else:
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                
                # Add title
                c.setFont("Helvetica-Bold", 16)
                c.drawString(1*inch, 10*inch, "Supporting Document")
                
                # Add file info
                c.setFont("Helvetica", 12)
                c.drawString(1*inch, 9.5*inch, f"File Name: {file_name}")
                c.drawString(1*inch, 9*inch, f"File Type: {file_ext.upper()}")
                c.drawString(1*inch, 8.5*inch, "File is not a PDF or image format.")
                c.drawString(1*inch, 8*inch, "Please open the original file in the system.")
                
                c.save()
                buffer.seek(0)
                return buffer


        except Exception as e:
            print(f"Error converting to PDF: {e}")
            
            # Create error page
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            c.setFont("Helvetica", 12)
            c.drawString(1*inch, 10*inch, f"Error processing file: {file_name}")
            c.save()
            buffer.seek(0)
            return buffer

    def update_file_remarks(self, file_id: int, remarks: Optional[str] = None) -> bool:
        """Update remarks for a specific file"""
        from src.models.base import WorkOrderFiles
        file = self.db.query(WorkOrderFiles).filter(WorkOrderFiles.id == file_id).first()
        if not file:
            return False
        
        file.remarks = remarks
        self.db.commit()
        return True
