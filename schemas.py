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

class AdminGrantAccessRequest(BaseModel):
    expiry_days: Optional[int] = Field(default=30, ge=1)
    plan_tier: Optional[str] = None
    reset_device: Optional[bool] = False
    is_tester: Optional[bool] = None

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
    is_tester: Optional[bool] = Field(False, example=False)

class AdminLoginRequest(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="SuperAdmin@2026")

class AdminLoginResponse(BaseModel):
    status: str = "success"
    admin_username: str
    token: str
    role: str = "superadmin"

class AdminStatsResponse(BaseModel):
    total_drivers: int
    active_drivers: int
    pending_drivers: int
    restricted_drivers: int
    blocked_drivers: int
    testers_count: int
    total_rides_today: int
    accepted_rides_today: int
    latest_app_version: str
    latest_adoption_count: int
    latest_adoption_percentage: float

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
    app_version: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
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
    screenshot_url: Optional[str] = None
    image_base64: Optional[str] = None
    system_min_fare: Optional[int] = None
    system_max_fare: Optional[int] = None
    system_max_distance: Optional[float] = None
    app_version: Optional[str] = None
    client_ride_id: Optional[str] = None
    latency_ms: Optional[int] = None

class RideVerifyRequest(BaseModel):
    driver_phone: str = Field(..., example="9876543210")
    client_ride_id: str = Field(..., example="3f2b8c1e-0c4a-4b7e-9d8e-1a2b3c4d5e6f")
    verified_status: str = Field(..., example="Accepted")
    verified_reason: Optional[str] = None

class DriverHeartbeatRequest(BaseModel):
    driver_phone: str = Field(..., example="9876543210")
    app_version: Optional[str] = None
    engine_connected: bool = True
    is_active: Optional[bool] = None
    trip_state: Optional[str] = None
    last_event_age_ms: Optional[int] = None
    error_count: Optional[int] = None
    last_error: Optional[str] = None
    enabled_platforms: Optional[int] = None

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
    screenshot_url: Optional[str] = None
    system_min_fare: Optional[int] = None
    system_max_fare: Optional[int] = None
    system_max_distance: Optional[float] = None
    app_version: Optional[str] = None
    client_ride_id: Optional[str] = None
    latency_ms: Optional[int] = None
    verified_status: Optional[str] = None
    verified_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScreenDumpCreate(BaseModel):
    driver_phone: str
    platform: str
    kind: str
    client_ride_id: Optional[str] = None
    app_version: Optional[str] = None
    device_model: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    screen_text: Optional[str] = None
    nodes_json: Optional[str] = None

class ScreenDumpSummary(BaseModel):
    id: int
    driver_phone: str
    platform: str
    kind: str
    client_ride_id: Optional[str] = None
    app_version: Optional[str] = None
    device_model: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScreenDumpDetail(ScreenDumpSummary):
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    screen_text: Optional[str] = None
    nodes_json: Optional[str] = None
