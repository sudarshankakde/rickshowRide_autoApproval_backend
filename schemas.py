from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class DriverRegisterRequest(BaseModel):
    name: str = Field(..., example="Rajesh Kumar")
    phone: str = Field(..., example="9876543210")
    password: str = Field(..., example="secret123")
    vehicle_number: Optional[str] = Field(None, example="MH12 AB 1234")
    city: Optional[str] = Field(None, example="Pune")
    language: Optional[str] = Field("mr", example="mr")
    device_id: str = Field(..., example="a1b2c3d4e5f6")

class DriverLoginRequest(BaseModel):
    phone: str = Field(..., example="9876543210")
    password: str = Field(..., example="secret123")
    device_id: str = Field(..., example="a1b2c3d4e5f6")

class DriverSettingsUpdate(BaseModel):
    phone: str
    device_id: str
    min_fare: int = Field(..., ge=0)
    max_fare: int = Field(..., ge=0)
    max_distance: Optional[float] = Field(5.0, ge=0.1)
    is_active: bool
    language: Optional[str] = Field(None, example="mr")

class AdminApproveRequest(BaseModel):
    expiry_days: int = Field(default=30, ge=1)

class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=4)

class AdminPlanUpdateRequest(BaseModel):
    plan_tier: str = Field(..., example="premium")

class AdminCustomPlatformsRequest(BaseModel):
    custom_allowed_platforms: Optional[list[str]] = Field(default=None)
    app_limit: Optional[int] = Field(default=None)

class AdminCreateDriverRequest(BaseModel):
    name: str = Field(..., example="Sudarshan Kakde")
    phone: str = Field(..., example="9021767520")
    password: str = Field(..., example="secret123")
    vehicle_number: Optional[str] = Field(None, example="MH12 AB 1234")
    city: Optional[str] = Field(None, example="Pune")
    plan_tier: Optional[str] = Field("premium", example="premium")
    status: Optional[str] = Field("active", example="active")
    expiry_days: Optional[int] = Field(30, ge=1)

class AdminLoginRequest(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="SuperAdmin@2026")

class AdminLoginResponse(BaseModel):
    status: str = "success"
    admin_username: str
    token: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class DriverResponse(BaseModel):
    id: int
    name: str
    phone: str
    device_id: str
    status: str
    vehicle_number: Optional[str] = None
    city: Optional[str] = None
    language: Optional[str] = "mr"
    expiry_date: Optional[date] = None
    min_fare: int
    max_fare: int
    max_distance: Optional[float] = 5.0
    is_active: bool
    is_tester: bool = False
    is_valid_subscription: bool = False
    plan_tier: Optional[str] = "premium"
    app_limit: int = 14
    allowed_platforms: Optional[list[str]] = None
    custom_allowed_platforms: Optional[list[str]] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RideLogCreate(BaseModel):
    driver_phone: str = Field(..., example="9876543210")
    platform: str = Field(..., example="Ola")
    fare: int = Field(..., example=220)
    pickup: Optional[str] = Field(None, example="Shivajinagar Station")
    drop: Optional[str] = Field(None, example="Kothrud Stand")
    distance: Optional[float] = Field(None, example=3.2)
    status: str = Field(..., example="accepted") # accepted, skipped
    reason: Optional[str] = Field(None, example="Auto-Accepted (Fare ₹220, Distance 3.2km <= 5.0km)")

class RideLogResponse(BaseModel):
    id: int
    driver_phone: str
    platform: str
    fare: int
    pickup: Optional[str] = None
    drop: Optional[str] = None
    distance: Optional[float] = None
    status: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
