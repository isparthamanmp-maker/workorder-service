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
class WorkOrdersCreateRequest(BaseModel):
    name: str
    formData: str
    workItems: str
    attachments: str
    authorizations: str
    tenderVendorData: str
    totalCost: float

    @validator('formData')
    def validate_form_data(cls, v):
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid formData JSON: {str(e)}")

    @validator('workItems')
    def validate_work_items(cls, v):
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("workItems must be a JSON array")
            return v
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid workItems JSON: {str(e)}")

    @validator('tenderVendorData')
    def validate_tender_vendor_data(cls, v):
        try:
            parsed = json.loads(v)
            TenderVendorDataSchema(**parsed)
            return v
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid tenderVendorData JSON: {str(e)}")

    def extract_work_order_data(self) -> Dict[str, Any]:
        """Extract and map data to work_orders table columns"""
        form_data = json.loads(self.formData)
        tender_data = json.loads(self.tenderVendorData)
        
        # Parse dates
        request_date = self._parse_date(form_data.get('date'))
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
            'document_number': form_data.get('worNo', '').strip(),
            'request_date': request_date,
            'request_type': 'work_order_request' if form_data.get('isWOR', False) else 'item_request',
            'submitted_by': submitted_by,
            'scope_of_works': form_data.get('scopeOfWork', '').strip(),
            'start_date': start_date,
            'end_date': end_date,
            'is_urgent': 1 if form_data.get('isUrgent', False) else 0,
            'budget_status': 'budgeted' if form_data.get('isBudgeted', True) else 'unbudgeted',
            'cost_type': form_data.get('costType', 'CAPEX'),
            'budget_index': form_data.get('budgetIndex', '').strip(),
            'budget_name': form_data.get('budgetName', '').strip(),
            'cost_estimation': float(form_data.get('costEstimation', 0)) or float(self.totalCost),
            'remaining_budget': float(form_data.get('budgetRemaining', 0)),
            'under_over': form_data.get('budgetUnderOver', '').strip(),
            'charge_to_tenant': 1 if form_data.get('chargeToTenant', False) else 0,
            'recommended_contractor': form_data.get('vendorName', '').strip(),
            'reason': form_data.get('vendorReason', '').strip(),
            'vendor_selection_method': vendor_selection_method,
            'test_and_analysis': tender_data.get('tenderDescription', '').strip(),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }

    def extract_work_items_data(self) -> List[Dict[str, Any]]:
        """Extract work items data for work_order_items table"""
        work_items = json.loads(self.workItems)
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
        attachments = json.loads(self.attachments)
        attachments_data = []
        
        # Define mapping between form field names and attachment types
        attachment_type_mapping = {
            'layout': 'layout',
            'documentation': 'documentation',
            'photoImages': 'photo_images',
            'billOfQuantity': 'bill_of_quantity'
        }
        
        for field_name, has_attachment in attachments.items():
            attachments_data.append({
                'document_type': attachment_type_mapping.get(field_name, field_name),
                'has_document': has_attachment
            })
        
        return attachments_data

    def extract_vendor_data(self) -> List[Dict[str, Any]]:
        """Extract vendor data for work_order_vendors table"""
        tender_data = json.loads(self.tenderVendorData)
        vendors_data = []
        
        for idx, vendor in enumerate(tender_data.get('vendors', [])):
            # Only add vendors that have a name (not empty)
            vendor_name = vendor.get('vendorName', '').strip()
            if vendor_name:
                vendors_data.append({
                    'vendor_name': vendor_name,
                    
                })
        
        return vendors_data

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
        """Map submitted_by value to database enum values"""
        if not submitted_value:
            return 'IT_Dept'  # Default value
        
        submitted_value = submitted_value.strip().lower()
        
        # Mapping common values to database enum values
        mapping = {
            'it dept': 'IT_Dept',
            'it dept.': 'IT_Dept',
            'it department': 'IT_Dept',
            'it': 'IT_Dept',
            'maresanm': 'Maresanm',
            'ops support': 'Ops_Support',
            'ops_support': 'Ops_Support',
            'ops-support': 'Ops_Support',
            'ops technical': 'Ops_Technical',
            'ops_technical': 'Ops_Technical',
            'ops-technical': 'Ops_Technical',
            'executive office': 'Executive_Office',
            'executive_office': 'Executive_Office',
            'executive-office': 'Executive_Office',
            'fin acc': 'Fin_Acc',
            'fin_acc': 'Fin_Acc',
            'fin-acc': 'Fin_Acc',
            'finance & accounting': 'Fin_Acc',
            'accounting': 'Fin_Acc',
            'finance': 'Fin_Acc',
        }
        
        # Check for exact match or partial match
        for key, value in mapping.items():
            if key in submitted_value:
                return value
        
        # Default to IT_Dept if no match found
        return 'IT_Dept'

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
    totalCost: float
    attachments: List[dict] = Field(default_factory=list)  # Optional with default
    authorizations: List[dict] = Field(default_factory=list)  # Optional with default
    
    class Config:
        from_attributes = True