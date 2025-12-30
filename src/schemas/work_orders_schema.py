from pydantic import BaseModel, Field, ConfigDict
from typing import Optional



# Schema for API responses
class WorkOrdersResponse(BaseModel):
    id: int
    document_number: str = None
    request_date: str = None
    request_type: str = None
    submitted_by: str = None
    scope_of_works: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
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
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


# Schema for creating records (no auto-generated fields)
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


# Optional: For backward compatibility or different naming preferences
class WorkOrdersResponseAlt(BaseModel):
    """Alternative response with database field names"""
    
    id: int
    document_number: str = None
    request_date: str = None
    request_type: str = None
    submitted_by: str = None
    scope_of_works: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
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
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )