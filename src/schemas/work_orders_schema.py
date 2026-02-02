# src/schemas/work_orders_schema.py
from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import json


# Schema for API responses
class WorkOrdersResponse(BaseModel):
    id: int
    document_number: str = None
    request_date: Optional[date] = None  # Changed from str to date
    request_type: str = None
    submitted_by: str = None
    scope_of_works: Optional[str] = None
    start_date: Optional[date] = None  # Changed from str to date
    end_date: Optional[date] = None    # Changed from str to date
    is_urgent: Optional[int] = None
    budget_status: Optional[str] = None
    cost_type: Optional[str] = None
    budget_index: Optional[str] = None
    budget_name: Optional[str] = None
    cost_estimation: Optional[float] = None
    remaining_budget: Optional[float] = None
    under_over: Optional[str] = None
    charge_to_tenant: Optional[int] = None
    recommended_contractor: Optional[str] = None
    reason: Optional[str] = None
    vendor_selection_method: Optional[str] = None
    test_and_analysis: Optional[str] = None
    created_at: Optional[datetime] = None  # Changed from str to datetime
    updated_at: Optional[datetime] = None  # Changed from str to datetime
    status: str = None
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


# Schema for creating records
class WorkOrdersCreate(BaseModel):
    document_number: str = Field(max_length=100)
    request_date: str
    request_type: str
    submitted_by: str
    scope_of_works: Optional[str] = Field(None)
    start_date: Optional[str] = Field(None)
    end_date: Optional[str] = Field(None)
    is_urgent: Optional[int] = Field(None)
    budget_status: Optional[str] = Field(None)
    cost_type: Optional[str] = Field(None)
    budget_index: Optional[str] = Field(None, max_length=50)
    budget_name: Optional[str] = Field(None, max_length=200)
    cost_estimation: Optional[float] = Field(None)
    remaining_budget: Optional[float] = Field(None)
    under_over: Optional[str] = Field(None, max_length=50)
    charge_to_tenant: Optional[int] = Field(None)
    recommended_contractor: Optional[str] = Field(None, max_length=200)
    reason: Optional[str] = Field(None)
    vendor_selection_method: Optional[str] = Field(None)
    test_and_analysis: Optional[str] = Field(None)
    created_at: Optional[str] = Field(None)
    updated_at: Optional[str] = Field(None)


# Schema for updating records
class WorkOrdersUpdate(BaseModel):
    id: Optional[int] = None
    document_number: Optional[str] = Field(None, max_length=100)
    request_date: Optional[str] = None
    request_type: Optional[str] = None
    submitted_by: Optional[str] = None
    scope_of_works: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_urgent: Optional[int] = None
    budget_status: Optional[str] = None
    cost_type: Optional[str] = None
    budget_index: Optional[str] = Field(None, max_length=50)
    budget_name: Optional[str] = Field(None, max_length=200)
    cost_estimation: Optional[float] = None
    remaining_budget: Optional[float] = None
    under_over: Optional[str] = Field(None, max_length=50)
    charge_to_tenant: Optional[int] = None
    recommended_contractor: Optional[str] = Field(None, max_length=200)
    reason: Optional[str] = None
    vendor_selection_method: Optional[str] = None
    test_and_analysis: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# Vendor schema based on your payload
class VendorSchema(BaseModel):
    id: int
    vendorName: Optional[str] = None
    

# Tender vendor data schema
class TenderVendorDataSchema(BaseModel):
    isTenderRequired: Optional[bool] = None
    tenderDescription: Optional[str] = None
    tenderDate: Optional[str] = None
    tenderEvaluationCriteria: Optional[str] = None
    vendors: List[VendorSchema] = []


# Main complex request schema
# Main complex request schema
class WorkOrdersCreateRequest(BaseModel):
    workOrder: dict  # This should contain form data
    workItems: List[dict]
    tenderVendorData: List[dict]  # Based on your payload, this is a list
    supportingDocuments: List[dict]
    authorizations: List[dict]
    totalCost: Optional[float] = 0.0

    # Remove the validators since they're causing issues
    # Pydantic will validate the types automatically
    
    def extract_work_order_data(self) -> Dict[str, Any]:
        """Extract and map data to work_orders table columns"""
        # Use workOrder directly (not formData)
        form_data = self.workOrder  
        
        # tenderVendorData is a list, not a dict
        tender_data = self.tenderVendorData[0] if self.tenderVendorData else {}  # Get first item or empty dict
        
        # Parse dates
        request_date = self._parse_date(form_data.get('requestDate'))
        start_date = self._parse_date(form_data.get('startDate'))
        end_date = self._parse_date(form_data.get('endDate'))
        
        # If request_date is None, use today's date (required field)
        if request_date is None:
            request_date = date.today()
        
        # Map submitted_by to database enum values
        submitted_by = self._map_submitted_by(
            form_data.get('submittedBy', '') or 
            form_data.get('submittedDivision', '')
        )
        
        # Map vendor_selection_method to database enum values
        vendor_selection_method = self._map_vendor_selection_method(
            form_data.get('vendorSelectionMethod', 'tender_process')
        )
        
        # Map formData fields to database columns
        return {
            'document_number': form_data.get('documentNumber', '').strip(),
            'request_date': request_date,
            'request_type': 'work_order_request' if form_data.get('isWOR', False) else 'item_request',
            'submitted_by': submitted_by,
        'scope_of_works': form_data.get('scopeOfWorks', '').strip(),
            'start_date': start_date,
            'end_date': end_date,
            'is_urgent': 1 if form_data.get('isUrgent', False) else 0,
            'budget_status': 'budgeted' if form_data.get('isBudgeted', True) else 'unbudgeted',
            'cost_type': form_data.get('costType', 'CAPEX'),
            'budget_index': form_data.get('budgetIndex', '').strip(),
            'budget_name': form_data.get('budgetName', '').strip(),
            'cost_estimation': float(form_data.get('costEstimation', 0)) or float(self.totalCost),
            'remaining_budget': float(form_data.get('remainingBudget', 0)),
        'under_over': form_data.get('underOver', '').strip(),
            'charge_to_tenant': 1 if form_data.get('chargeToTenant', False) else 0,
        'recommended_contractor': form_data.get('recommendedContractor', '').strip(),
        'reason': form_data.get('reason', '').strip(),
            'vendor_selection_method': vendor_selection_method,
            'test_and_analysis': tender_data.get('tenderDescription', '').strip(),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }

    def extract_work_items_data(self) -> List[Dict[str, Any]]:
        """Extract work items data for work_order_items table"""
        # Use workItems directly (it's already a list)
        work_items = self.workItems  
        items_data = []
        
        for idx, item in enumerate(work_items):
            items_data.append({
                'description': item.get('description', ''),
                'quantity': float(item.get('quantity', 1)),
                'unit_price': float(item.get('unitPrice', 0)),
                'total_price': float(item.get('quantity', 1)) * float(item.get('unitPrice', 0)),
                'item_order': idx + 1
            })
        
        return items_data

    def extract_attachments_data(self) -> List[Dict[str, Any]]:
        """Extract attachments data for attachments table"""
        # Use supportingDocuments directly
        attachments = self.supportingDocuments  
        attachments_data = []
        
        for doc in attachments:
            attachments_data.append({
                'document_type': doc.get('documentType', ''),
                'has_document': doc.get('hasDocument', False)
            })
        
        return attachments_data

    def extract_vendor_data(self) -> List[Dict[str, Any]]:
        """Extract vendor data for work_order_vendors table"""
        # Use tenderVendorData directly (it's already a list)
        tender_data = self.tenderVendorData  
        vendors_data = []
        
        # If tenderVendorData is a list of dicts
        for idx, vendor in enumerate(tender_data):
            vendor_name = vendor.get('vendorName', '').strip()
            if vendor_name:
                vendors_data.append({
                    'vendor_name': vendor_name,
                })
        
        return vendors_data

    def extract_authorizations_data(self) -> List[Dict[str, Any]]:
        """Extract authorizations data for authorizations table"""
        # Use authorizations directly (it's already a list)
        authorizations = self.authorizations  
        authorizations_data = []
        
        for auth in authorizations:
            person_name = auth.get('name', '').strip()
            date_str = auth.get('date', '').strip()
            
            if person_name:
                auth_date = self._parse_date(date_str) if date_str else None
                
                authorizations_data.append({
                    'authorization_type': auth.get('role', ''),
                    'person_name': person_name,
                    'authorization_date': auth_date
                })
        
        return authorizations_data
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object - handle multiple formats"""
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        
        # Try multiple date formats
        date_formats = [
            '%Y-%m-%d',        # 2025-12-30
            '%d %b %Y',        # 30 Dec 2025
            '%d/%m/%Y',        # 30/12/2025
            '%m/%d/%Y',        # 12/30/2025
            '%Y/%m/%d',        # 2025/12/30
        ]
        
        for date_format in date_formats:
            try:
                return datetime.strptime(date_str, date_format).date()
            except ValueError:
                continue
        
        return None

    def _map_submitted_by(self, submitted_value: str) -> str:
        return submitted_value

    def _map_vendor_selection_method(self, method: str) -> str:
        """Map vendor selection method to database enum values"""
        if not method:
            return 'sole_source_vendor'  # Default
        
        method = method.strip().lower()
        
        mapping = {
            'tender process': 'tender_process',
            'tender': 'tender_process',
            'tender_process': 'tender_process',
            'tender-process': 'tender_process',
            'sole source vendor': 'sole_source_vendor',
            'sole source': 'sole_source_vendor',
            'sole_source_vendor': 'sole_source_vendor',
            'sole-source-vendor': 'sole_source_vendor',
            'sole': 'sole_source_vendor',
        }
        
        for key, value in mapping.items():
            if key in method:
                return value
        
        # Default
        return 'sole_source_vendor'
    

# Add this to src/schemas/work_orders_schema.py
class WorkOrdersGetResponse(BaseModel):
    """Response schema for GET that matches POST payload structure"""
    name: str
    formData: str
    workItems: str
    attachments: str
    authorizations: str
    tenderVendorData: str
    totalCost: float
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )

class WorkOrdersFullResponse(BaseModel):
    id: int
    workOrder: dict
    workItems: List[dict]
    tenderVendorData: List[dict]  # Keep as list
    supportingDocuments: List[dict]
    totalCost: float
    attachments: List[dict] = Field(default_factory=list)  # Optional with default
    authorizations: List[dict] = Field(default_factory=list)  # Optional with default
    
    class Config:
        from_attributes = True


# src/schemas/work_orders_schema.py
# Add these schemas at the bottom of the file

class GenerateDocumentNumberRequest(BaseModel):
    submitted_by: str = Field(
        ..., 
        description="The department/person submitting the work order",
        examples=["IT_Dept", "Executive_Office", "Ops_Support"]
    )

class DocumentNumberResponse(BaseModel):
    document_number: str
    submitted_by: str
    year: int
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )

class WorkOrdersUpdateRequest(BaseModel):
    """Schema for updating work orders (accepts GET response structure)"""
    workOrder: dict
    workItems: List[dict]
    tenderVendorData: List[dict]
    supportingDocuments: List[dict]
    authorizations: List[dict]
    totalCost: Optional[float] = 0.0

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )

    def convert_to_create_request_format(self) -> WorkOrdersCreateRequest:
        """Convert update format to create request format"""
        import json
        
        print(f"\nDEBUG: Converting update request to create format")
        print(f"workOrder type: {type(self.workOrder)}")
        print(f"workItems type: {type(self.workItems)}, length: {len(self.workItems)}")
        print(f"supportingDocuments type: {type(self.supportingDocuments)}, length: {len(self.supportingDocuments)}")
        print(f"authorizations type: {type(self.authorizations)}")
        print(f"tenderVendorData type: {type(self.tenderVendorData)}, length: {len(self.tenderVendorData)}")
        
        # Convert workOrder to formData dict
        form_data_dict = {
            "worNo": self.workOrder.get("documentNumber", ""),
            "date": self.workOrder.get("requestDate", ""),
            "requestType": "work_order_request" if self.workOrder.get("requestType") == "work_order_request" else "item_request",
            "submittedBy": self.workOrder.get("submittedBy", ""),
            "submittedDivision": self.workOrder.get("submittedBy", ""),
            "scopeOfWork": self.workOrder.get("scopeOfWorks", ""),
            "startDate": self.workOrder.get("startDate", ""),
            "endDate": self.workOrder.get("endDate", ""),
            "isUrgent": bool(self.workOrder.get("isUrgent", False)),
            "isBudgeted": self.workOrder.get("budgetStatus") == "budgeted",
            "costType": self.workOrder.get("costType", "CAPEX"),
            "budgetIndex": self.workOrder.get("budgetIndex", ""),
            "budgetName": self.workOrder.get("budgetName", ""),
            "costEstimation": float(self.workOrder.get("costEstimation", 0)),
            "budgetRemaining": float(self.workOrder.get("remainingBudget", 0)),
            "budgetUnderOver": self.workOrder.get("underOver", ""),
            "chargeToTenant": bool(self.workOrder.get("chargeToTenant", False)),
            "vendorName": self.workOrder.get("recommendedContractor", ""),
            "vendorReason": self.workOrder.get("reason", ""),
            "vendorSelectionMethod": self.workOrder.get("vendorSelectionMethod", "tender_process"),
            "isWOR": self.workOrder.get("requestType") == "work_order_request",
        }
        
        print(f"\nDEBUG: Created form_data_dict with keys: {list(form_data_dict.keys())}")
        
        # Convert workItems
        work_items_list = []
        for idx, item in enumerate(self.workItems):
            work_items_list.append({
                "description": item.get("description", ""),
                "quantity": float(item.get("quantity", 1)),
                "unitPrice": float(item.get("unitPrice", 0))
            })
        
        print(f"DEBUG: Created {len(work_items_list)} work items")
        
        # Process supportingDocuments
        supporting_docs_list = []
        
        for doc_idx, doc in enumerate(self.supportingDocuments):
            document_type = doc.get("documentType", "")
            files = doc.get("files", [])
            has_document = doc.get("hasDocument", False) or len(files) > 0
            
            file_list = []
            for file_idx, file in enumerate(files):
                # Get filename
                file_name = file.get('fileName') or file.get('filename') or f"file_{file_idx+1}"
                
                # Get action
                action = file.get('action', 'new')
                
                # Get file content
                file_content = None
                for field in ['fileContent', 'filecontent', 'content', 'data']:
                    if field in file:
                        file_content = file[field]
                        break
                
                if action in ['existing', 'keep', 'unchanged']:
                    file_list.append({
                        "fileName": file_name,
                        "fileContent": "",  # Empty for existing files
                        "action": "existing"
                    })
                elif action in ['new', 'add', 'upload']:
                    if file_content and len(str(file_content)) > 10:
                        file_list.append({
                            "fileName": file_name,
                            "fileContent": file_content,
                            "action": "new"
                        })
                    else:
                        file_list.append({
                            "fileName": file_name,
                            "fileContent": "",
                            "action": "existing"  # Treat as existing since no content
                        })
                else:
                    file_list.append({
                        "fileName": file_name,
                        "fileContent": file_content or "",
                        "action": "new" if file_content and len(str(file_content)) > 10 else "existing"
                    })
            
            supporting_docs_list.append({
                "documentType": document_type,
                "hasDocument": has_document,
                "files": file_list
            })
        
        print(f"DEBUG: Created {len(supporting_docs_list)} supporting documents")
        
        # Process authorizations
        authorizations_list = []
        
        # Check if authorizations is a list
        if isinstance(self.authorizations, list):
            for auth in self.authorizations:
                if isinstance(auth, dict):
                    authorizations_list.append({
                        "role": auth.get("role", ""),
                        "name": auth.get("name", ""),
                        "date": auth.get("date", "")
                    })
        # Check if authorizations is a dict (from old format)
        elif isinstance(self.authorizations, dict):
            # Convert from dict format to list format
            auth_mapping = {
                "preparedBy": "prepared_by",
                "deptHeadName": "department_head",
                "accDeptName": "accounting_department",
                "bmName": "business_manager",
                "directorName": "director",
                "purchasingName": "purchasing"
            }
            
            date_mapping = {
                "preparedBy": "preparedDate",
                "deptHeadName": "deptHeadDate",
                "accDeptName": "accDeptDate",
                "bmName": "bmDate",
                "directorName": "directorDate",
                "purchasingName": "purchasingDate"
            }
            
            for name_field, role in auth_mapping.items():
                name = self.authorizations.get(name_field, "")
                date_field = date_mapping.get(name_field, "")
                date_val = self.authorizations.get(date_field, "")
                
                if name:
                    authorizations_list.append({
                        "role": role,
                        "name": name,
                        "date": date_val
                    })
        
        print(f"DEBUG: Created {len(authorizations_list)} authorizations")
        
        # Process tenderVendorData
        tender_vendor_list = []
        
        for vendor in self.tenderVendorData:
            if isinstance(vendor, dict):
                vendor_name = vendor.get("vendorName", "")
                if vendor_name and vendor_name.strip():
                    tender_vendor_list.append({
                        "id": vendor.get("id", 0),
                        "vendorName": vendor_name.strip()
                    })
        
        print(f"DEBUG: Created {len(tender_vendor_list)} tender vendors")
        
        # Calculate total cost
        total_cost = self.totalCost
        if total_cost == 0:
            total_cost = sum(item.get("totalPrice", 0) for item in self.workItems)
        
        print(f"DEBUG: Total cost: {total_cost}")
        
        # Create and return WorkOrdersCreateRequest
        create_request = WorkOrdersCreateRequest(
            workOrder=form_data_dict,
            workItems=work_items_list,
            supportingDocuments=supporting_docs_list,
            authorizations=authorizations_list,
            tenderVendorData=tender_vendor_list,
            totalCost=total_cost
        )
        
        print(f"DEBUG: Successfully created WorkOrdersCreateRequest")
        return create_request
