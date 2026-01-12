from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# Schema for API responses
class WorkOrdersHistoryResponse(BaseModel):
    id: int
    status: str
    refid: int
    refnum: str
    refvalue: Optional[float] = None
    created_at: Optional[datetime] = None  # Use datetime type
    created_by: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
class WorkOrdersHistoryCreate(BaseModel):
    status: str = Field(..., max_length=100)
    refid: int = Field(...)
    refnum: str = Field(..., max_length=100)
    refvalue: Optional[float] = Field(None)
    created_by: Optional[str] = Field(None, max_length=100)
    
    model_config = ConfigDict(from_attributes=True)


# Schema for updating records
class WorkOrdersHistoryUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=100)
    refid: Optional[int] = None
    refnum: Optional[str] = Field(None, max_length=100)
    refvalue: Optional[float] = None
    created_by: Optional[str] = Field(None, max_length=100)
    
    model_config = ConfigDict(from_attributes=True)


# Optional: For backward compatibility or different naming preferences
class WorkOrdersHistoryResponseAlt(BaseModel):
    """Alternative response with database field names"""
    
    id: int
    status: str = None
    refid: int = None
    refnum: str = None
    refvalue: Optional[float] = None
    created_at: str = None
    created_by: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
