import datetime
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, EmailStr, Field

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# Calculation Schemas
class CalculationCreate(BaseModel):
    calculation_type: str
    expression_input: str
    expression_output: str  # JSON-encoded details
    is_saved: bool = False

class CalculationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    calculation_type: str
    expression_input: str
    expression_output: str  # Decoded back or stringified JSON
    is_saved: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MathSolveRequest(BaseModel):
    expression: str
    options: Optional[Dict[str, Any]] = None

class MatrixRequest(BaseModel):
    matrix_a: List[List[float]]
    matrix_b: Optional[List[List[float]]] = None
    operation: str  # "add", "subtract", "multiply", "determinant", "transpose", "invert", "eigenvalues"
    scalar: Optional[float] = None

class UnitConversionRequest(BaseModel):
    value: float
    from_unit: str
    to_unit: str
    category: str # "length", "area", "volume", "mass", "temperature", "speed"

# Admin Schemas
class AdminReportCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    content: str = Field(..., min_length=10)

class AdminReportUpdate(BaseModel):
    status: str  # "open", "in_progress", "resolved"

class AdminReportResponse(BaseModel):
    id: int
    reporter_id: int
    title: str
    content: str
    status: str
    created_at: datetime.datetime
    reporter: Optional[UserResponse] = None

    class Config:
        from_attributes = True

# Activity Log Schema
class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime.datetime
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True

# Dashboard Stats Response
class DashboardStats(BaseModel):
    total_calculations: int
    saved_calculations: int
    recent_activity_count: int
    categories_breakdown: Dict[str, int]

# Password Reset Schemas
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

