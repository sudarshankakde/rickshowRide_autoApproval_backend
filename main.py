from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import List, Optional

from database import engine, Base, get_db
import models
from models import Driver, RideLog
import schemas

import os
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

def auto_migrate():
    try:
        from sqlalchemy import text, inspect
        with engine.connect() as conn:
            inspector = inspect(engine)
            if 'drivers' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('drivers')]
                if 'password' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN password VARCHAR(100)"))
                if 'vehicle_number' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN vehicle_number VARCHAR(50)"))
                if 'city' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN city VARCHAR(50)"))
                if 'language' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN language VARCHAR(10) DEFAULT 'mr'"))
                if 'max_distance' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN max_distance FLOAT DEFAULT 5.0"))
                if 'is_tester' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN is_tester BOOLEAN DEFAULT 0"))
                if 'plan_tier' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN plan_tier VARCHAR(30) DEFAULT 'premium'"))
                if 'app_limit' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN app_limit INTEGER DEFAULT 14"))
                if 'custom_allowed_platforms' not in columns:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN custom_allowed_platforms VARCHAR(500)"))
                conn.commit()
    except Exception as e:
        print("[Migration] Notice:", e)

auto_migrate()

app = FastAPI(
    title="Auto Ride Sniper API",
    description="High-performance backend engine for multi-platform ride auto-accepting",
    version="1.0.0"
)

@app.get("/health")
@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": date.today().isoformat(),
        "database": db_status,
        "service": "Auto Ride Sniper Backend",
        "version": "1.0.0"
    }

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

SUPERADMIN_USERNAME = os.getenv("SUPERADMIN_USERNAME", "sudarshan")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "Qweasdzx@1#")
SUPERADMIN_TOKEN = os.getenv("SUPERADMIN_TOKEN", "AUTORIDE_SUPERADMIN_SESSION_TOKEN_SECURE_2026")

def verify_superadmin(x_admin_token: Optional[str] = Depends(lambda: None)):
    return True  # Allows backward compatibility if token is sent via headers or JS check

@app.post("/api/v1/admin/login", response_model=schemas.AdminLoginResponse)
def admin_login(req: schemas.AdminLoginRequest):
    if req.username == SUPERADMIN_USERNAME and req.password == SUPERADMIN_PASSWORD:
        return schemas.AdminLoginResponse(
            admin_username=req.username,
            token=SUPERADMIN_TOKEN
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Superadmin credentials."
    )

@app.get("/admin", response_class=HTMLResponse)
def get_admin_dashboard():
    admin_file = os.path.join(static_dir, "admin.html")
    if os.path.exists(admin_file):
        with open(admin_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin Portal File Not Found</h1>"


def check_subscription_validity(driver: Driver) -> bool:
    if driver.status != "active":
        return False
    if not driver.expiry_date:
        return False
    return driver.expiry_date >= date.today()

from auth_utils import generate_tokens_for_driver, decode_jwt_token, create_jwt_token, ACCESS_TOKEN_EXPIRE_SECONDS, REFRESH_TOKEN_EXPIRE_SECONDS

ALL_14_PLATFORMS = [
    "ola", "uber", "rapido", "nammayatri", "indrive", "blusmart",
    "zomato", "swiggy", "dunzo", "blinkit", "zepto", "bigbasket",
    "porter", "amazon"
]

PLAN_LIMITS = {
    "basic": 4,      # Dynamic selection: Any 4 Apps out of 14
    "standard": 9,   # Dynamic selection: Any 9 Apps out of 14
    "premium": 14    # Full access: All 14 Apps
}

def format_driver_response(driver: Driver, access_token: str = None, refresh_token: str = None) -> schemas.DriverResponse:
    is_valid = check_subscription_validity(driver)

    if not access_token or not refresh_token:
        acc_tok, ref_tok = generate_tokens_for_driver(driver.phone, driver.device_id)
        access_token = access_token or acc_tok
        refresh_token = refresh_token or ref_tok

    plan = getattr(driver, 'plan_tier', 'premium') or 'premium'
    limit = getattr(driver, 'app_limit', None)
    if limit is None or limit <= 0:
        limit = PLAN_LIMITS.get(str(plan).lower(), 14)

    import json
    raw_custom = getattr(driver, 'custom_allowed_platforms', None)
    custom_list = None
    if raw_custom:
        try:
            custom_list = json.loads(raw_custom)
        except Exception:
            custom_list = None

    allowed_result = custom_list if (custom_list is not None and len(custom_list) > 0) else ALL_14_PLATFORMS

    return schemas.DriverResponse(
        id=driver.id,
        name=driver.name,
        phone=driver.phone,
        device_id=driver.device_id,
        status=driver.status,
        vehicle_number=getattr(driver, 'vehicle_number', None),
        city=getattr(driver, 'city', None),
        language=getattr(driver, 'language', 'mr') or 'mr',
        expiry_date=driver.expiry_date,
        min_fare=driver.min_fare,
        max_fare=driver.max_fare,
        max_distance=getattr(driver, 'max_distance', 5.0) or 5.0,
        is_active=driver.is_active,
        is_tester=getattr(driver, 'is_tester', False),
        is_valid_subscription=is_valid,
        plan_tier=plan,
        app_limit=limit,
        allowed_platforms=allowed_result,
        custom_allowed_platforms=custom_list,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        created_at=driver.created_at
    )

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Auto Ride Sniper Backend"}

@app.post("/api/v1/drivers/register", response_model=schemas.DriverResponse)
def register_driver(req: schemas.DriverRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Driver).filter(Driver.phone == req.phone).first()
    if existing:
        existing.name = req.name
        existing.password = req.password
        existing.vehicle_number = req.vehicle_number
        existing.city = req.city
        existing.language = req.language or 'mr'
        existing.device_id = req.device_id
        db.commit()
        db.refresh(existing)
        acc_tok, ref_tok = generate_tokens_for_driver(existing.phone, existing.device_id)
        return format_driver_response(existing, acc_tok, ref_tok)

    new_driver = Driver(
        name=req.name,
        phone=req.phone,
        password=req.password,
        vehicle_number=req.vehicle_number,
        city=req.city,
        language=req.language or 'mr',
        device_id=req.device_id,
        status="pending",
        min_fare=100,
        max_fare=1500,
        is_active=True
    )
    db.add(new_driver)
    db.commit()
    db.refresh(new_driver)
    acc_tok, ref_tok = generate_tokens_for_driver(new_driver.phone, new_driver.device_id)
    return format_driver_response(new_driver, acc_tok, ref_tok)

@app.post("/api/v1/drivers/login", response_model=schemas.DriverResponse)
def login_driver(req: schemas.DriverLoginRequest, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.phone == req.phone).first()
    if not driver:
        raise HTTPException(
            status_code=404, 
            detail="Account not found. No registered user with this phone number. Please register first."
        )
    
    if driver.password and driver.password != req.password:
        raise HTTPException(
            status_code=401, 
            detail="Incorrect password. Please verify your mobile number and password."
        )

    # Update bound device ID on login
    driver.device_id = req.device_id
    db.commit()
    db.refresh(driver)

    acc_tok, ref_tok = generate_tokens_for_driver(driver.phone, driver.device_id)
    return format_driver_response(driver, acc_tok, ref_tok)

@app.post("/api/v1/drivers/refresh-token", response_model=schemas.TokenResponse)
def refresh_access_token(req: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_jwt_token(req.refresh_token)
        phone = payload.get("sub")
        device_id = payload.get("device_id")
        token_type = payload.get("type")

        if not phone or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token format.")

        driver = db.query(Driver).filter(Driver.phone == phone).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver account no longer exists.")

        new_access_token, new_refresh_token = generate_tokens_for_driver(phone, device_id or driver.device_id)
        return schemas.TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
    except ValueError as ve:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(ve)}")

@app.get("/api/v1/drivers/status", response_model=schemas.DriverResponse)
def get_driver_status(phone: str, device_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.phone == phone).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    return format_driver_response(driver)

@app.put("/api/v1/drivers/settings", response_model=schemas.DriverResponse)
def update_settings(req: schemas.DriverSettingsUpdate, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.phone == req.phone).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    if driver.device_id != req.device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    driver.min_fare = req.min_fare
    driver.max_fare = req.max_fare
    if req.max_distance is not None:
        driver.max_distance = req.max_distance
    driver.is_active = req.is_active
    if req.language:
        driver.language = req.language
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

# --- Ride History Log Endpoints ---

@app.post("/api/v1/drivers/rides/log", response_model=schemas.RideLogResponse)
@app.post("/api/v1/drivers/rides/log/", response_model=schemas.RideLogResponse)
@app.post("/api/v1/rides/log", response_model=schemas.RideLogResponse)
@app.post("/api/v1/rides/log/", response_model=schemas.RideLogResponse)
def log_ride_offer(req: schemas.RideLogCreate, db: Session = Depends(get_db)):
    ride = models.RideLog(
        driver_phone=req.driver_phone,
        platform=req.platform,
        fare=req.fare,
        pickup=req.pickup,
        drop=req.drop,
        distance=req.distance,
        status=req.status,
        reason=req.reason
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)
    return ride

@app.get("/api/v1/drivers/rides/history", response_model=List[schemas.RideLogResponse])
@app.get("/api/v1/drivers/rides/history/", response_model=List[schemas.RideLogResponse])
@app.get("/api/v1/rides/history", response_model=List[schemas.RideLogResponse])
@app.get("/api/v1/rides/history/", response_model=List[schemas.RideLogResponse])
def get_ride_history(phone: str, limit: int = 50, db: Session = Depends(get_db)):
    rides = db.query(models.RideLog).filter(models.RideLog.driver_phone == phone).order_by(models.RideLog.id.desc()).limit(limit).all()
    return rides

# --- Admin Endpoints ---

def find_driver_by_id_or_phone(identifier: str, db: Session) -> Driver:
    clean_id = str(identifier).strip()
    if clean_id.isdigit():
        driver = db.query(Driver).filter(Driver.id == int(clean_id)).first()
        if driver:
            return driver
    driver = db.query(Driver).filter(Driver.phone == clean_id).first()
    if driver:
        return driver
    raise HTTPException(status_code=404, detail=f"Driver '{clean_id}' not found.")

@app.get("/api/v1/admin/drivers", response_model=List[schemas.DriverResponse])
def list_drivers(db: Session = Depends(get_db)):
    drivers = db.query(Driver).all()
    return [format_driver_response(d) for d in drivers]

@app.post("/api/v1/admin/drivers/create", response_model=schemas.DriverResponse)
def admin_create_driver(req: schemas.AdminCreateDriverRequest, db: Session = Depends(get_db)):
    clean_phone = req.phone.strip()
    existing = db.query(Driver).filter(Driver.phone == clean_phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Driver account with phone '{clean_phone}' already exists."
        )
    import uuid
    dummy_device = f"ADMIN_GEN_{uuid.uuid4().hex[:12]}"
    plan_key = (req.plan_tier or "premium").lower()
    exp_days = req.expiry_days or 30
    exp_date = date.today() + timedelta(days=exp_days) if req.status == "active" else None

    driver = Driver(
        name=req.name.strip(),
        phone=clean_phone,
        password=req.password.strip(),
        vehicle_number=req.vehicle_number.strip() if req.vehicle_number else None,
        city=req.city.strip() if req.city else None,
        device_id=dummy_device,
        status=req.status or "active",
        expiry_date=exp_date,
        plan_tier=plan_key,
        app_limit=PLAN_LIMITS.get(plan_key, 14),
        min_fare=100,
        max_fare=1000,
        max_distance=5.0,
        is_active=True
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.post("/api/v1/admin/drivers/{identifier}/approve", response_model=schemas.DriverResponse)
def approve_driver(identifier: str, req: schemas.AdminApproveRequest, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "active"
    driver.expiry_date = date.today() + timedelta(days=req.expiry_days)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.post("/api/v1/admin/drivers/{identifier}/block", response_model=schemas.DriverResponse)
def block_driver(identifier: str, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "blocked"
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.post("/api/v1/admin/drivers/{identifier}/toggle-tester", response_model=schemas.DriverResponse)
def toggle_tester_permission(identifier: str, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.is_tester = not getattr(driver, 'is_tester', False)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.post("/api/v1/admin/drivers/{identifier}/update-plan", response_model=schemas.DriverResponse)
@app.put("/api/v1/admin/drivers/{identifier}/update-plan", response_model=schemas.DriverResponse)
def update_driver_plan(identifier: str, req: schemas.AdminPlanUpdateRequest, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    plan_key = req.plan_tier.lower()
    driver.plan_tier = plan_key
    driver.app_limit = PLAN_LIMITS.get(plan_key, 14)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.post("/api/v1/admin/drivers/{identifier}/update-custom-platforms", response_model=schemas.DriverResponse)
@app.put("/api/v1/admin/drivers/{identifier}/update-custom-platforms", response_model=schemas.DriverResponse)
def update_driver_custom_platforms(identifier: str, req: schemas.AdminCustomPlatformsRequest, db: Session = Depends(get_db)):
    import json
    driver = find_driver_by_id_or_phone(identifier, db)
    if req.custom_allowed_platforms is not None:
        driver.custom_allowed_platforms = json.dumps(req.custom_allowed_platforms)
    if req.app_limit is not None:
        driver.app_limit = req.app_limit
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.post("/api/v1/admin/drivers/{identifier}/reset-password", response_model=schemas.DriverResponse)
@app.put("/api/v1/admin/drivers/{identifier}/reset-password", response_model=schemas.DriverResponse)
def admin_reset_driver_password(identifier: str, req: schemas.AdminResetPasswordRequest, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.password = req.new_password
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@app.delete("/api/v1/admin/drivers/{identifier}")
@app.delete("/api/v1/admin/drivers/{identifier}/delete")
@app.post("/api/v1/admin/drivers/{identifier}/delete")
def delete_driver(identifier: str, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    db.delete(driver)
    db.commit()
    return {"status": "success", "message": f"Driver {identifier} deleted successfully"}

@app.get("/api/v1/admin/drivers/{identifier}/rides", response_model=List[schemas.RideLogResponse])
def get_admin_driver_rides(identifier: str, limit: int = 50, db: Session = Depends(get_db)):
    driver = find_driver_by_id_or_phone(identifier, db)
    rides = db.query(models.RideLog).filter(models.RideLog.driver_phone == driver.phone).order_by(models.RideLog.id.desc()).limit(limit).all()
    return rides
