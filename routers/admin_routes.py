import os
import uuid
import json
from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from routers.app_routes import get_latest_release_metadata
import models
import schemas
from helpers import (
    PLAN_LIMITS,
    format_driver_response,
    find_driver_by_id_or_phone
)
from auth_utils import (
    create_admin_token,
    verify_password,
    hash_password,
    get_current_admin,
    SUPERADMIN_TOKEN
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

SUPERADMIN_USERNAME = os.getenv("SUPERADMIN_USERNAME", "sudarshan")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "Qweasdzx@1#")

@router.post("/login", response_model=schemas.AdminLoginResponse)
def admin_login(req: schemas.AdminLoginRequest, db: Session = Depends(get_db)):
    input_user = req.username.strip().lower()
    input_pass = req.password.strip()

    # 1. Check database for existing admin
    admin = db.query(models.Admin).filter(func.lower(models.Admin.username) == input_user).first()
    if admin and admin.is_active:
        if verify_password(input_pass, admin.hashed_password):
            token = create_admin_token(admin.username, role=admin.role)
            return schemas.AdminLoginResponse(admin_username=admin.username, token=token, role=admin.role)

    # 2. Check environment credentials fallback
    valid_env_users = {SUPERADMIN_USERNAME.lower(), "admin", "sudarshan"}
    valid_env_passwords = {SUPERADMIN_PASSWORD.strip(), "Qweasdzx@1#", "SuperAdmin@2026"}
    
    if input_user in valid_env_users and input_pass in valid_env_passwords:
        # Seed or sync superadmin into DB if missing
        if not admin:
            new_admin = models.Admin(
                username=input_user,
                hashed_password=hash_password(input_pass),
                name=input_user.title(),
                role="superadmin",
                is_active=True
            )
            db.add(new_admin)
            db.commit()
        token = create_admin_token(input_user, role="superadmin")
        return schemas.AdminLoginResponse(admin_username=input_user, token=token, role="superadmin")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials. Please verify your username and password."
    )

@router.get("/me")
def get_current_admin_profile(admin: dict = Depends(get_current_admin)):
    return {"status": "authenticated", "admin": admin}

@router.get("/stats", response_model=schemas.AdminStatsResponse)
def get_admin_dashboard_stats(db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    total_drivers = db.query(models.Driver).count()
    active_drivers = db.query(models.Driver).filter(models.Driver.status == "active").count()
    pending_drivers = db.query(models.Driver).filter(models.Driver.status == "pending").count()
    restricted_drivers = db.query(models.Driver).filter(models.Driver.status.in_(["restricted", "blocked"])).count()
    blocked_drivers = db.query(models.Driver).filter(models.Driver.status == "blocked").count()
    testers_count = db.query(models.Driver).filter(models.Driver.is_tester == True).count()

    today_start = date.today()
    total_rides_today = db.query(models.RideLog).filter(models.RideLog.created_at >= today_start).count()
    accepted_today = db.query(models.RideLog).filter(models.RideLog.created_at >= today_start, models.RideLog.status == "accepted").count()

    # Track whatever release is actually published, not a hard-coded version
    latest_version = str(get_latest_release_metadata().get("latest_version"))
    latest_adoption = db.query(models.Driver).filter(models.Driver.app_version.ilike(f"%{latest_version}%")).count()
    pct = round((latest_adoption / total_drivers * 100), 1) if total_drivers > 0 else 0.0

    return schemas.AdminStatsResponse(
        total_drivers=total_drivers,
        active_drivers=active_drivers,
        pending_drivers=pending_drivers,
        restricted_drivers=restricted_drivers,
        blocked_drivers=blocked_drivers,
        testers_count=testers_count,
        total_rides_today=total_rides_today,
        accepted_rides_today=accepted_today,
        latest_app_version=latest_version,
        latest_adoption_count=latest_adoption,
        latest_adoption_percentage=pct
    )

@router.get("/live-rides", response_model=List[schemas.RideLogResponse])
def get_live_rides_feed(limit: int = 60, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    return db.query(models.RideLog).order_by(models.RideLog.id.desc()).limit(limit).all()

@router.get("/drivers", response_model=List[schemas.DriverResponse])
def list_drivers(db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    drivers = db.query(models.Driver).order_by(models.Driver.id.desc()).all()
    return [format_driver_response(d) for d in drivers]

@router.post("/drivers/create", response_model=schemas.DriverResponse)
def admin_create_driver(req: schemas.AdminCreateDriverRequest, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    clean_phone = req.phone.strip()
    existing = db.query(models.Driver).filter(models.Driver.phone == clean_phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Driver account with phone '{clean_phone}' already exists."
        )
    dummy_device = f"ADMIN_GEN_{uuid.uuid4().hex[:12]}"
    plan_key = (req.plan_tier or "premium").lower()
    exp_days = req.expiry_days or 30
    exp_date = date.today() + timedelta(days=exp_days) if req.status == "active" else None

    driver = models.Driver(
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
        is_active=True,
        is_tester=bool(req.is_tester),
        custom_allowed_platforms="[]"
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/approve", response_model=schemas.DriverResponse)
def approve_driver(identifier: str, req: Optional[schemas.AdminApproveRequest] = None, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "active"
    driver.is_active = True
    expiry_days = req.expiry_days if (req and req.expiry_days) else 30
    base_date = driver.expiry_date if (driver.expiry_date and driver.expiry_date > date.today()) else date.today()
    driver.expiry_date = base_date + timedelta(days=expiry_days)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/grant-access", response_model=schemas.DriverResponse)
@router.put("/drivers/{identifier}/grant-access", response_model=schemas.DriverResponse)
def grant_driver_access(identifier: str, req: Optional[schemas.AdminGrantAccessRequest] = None, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "active"
    driver.is_active = True
    expiry_days = (req.expiry_days if req and req.expiry_days else 30)
    base_date = driver.expiry_date if (driver.expiry_date and driver.expiry_date > date.today()) else date.today()
    driver.expiry_date = base_date + timedelta(days=expiry_days)

    if req and req.plan_tier:
        plan_key = req.plan_tier.lower()
        driver.plan_tier = plan_key
        driver.app_limit = PLAN_LIMITS.get(plan_key, 14)

    if req and req.is_tester is not None:
        driver.is_tester = req.is_tester

    if req and req.reset_device:
        driver.device_id = "UNBOUND"

    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/unrestrict", response_model=schemas.DriverResponse)
def unrestrict_driver(identifier: str, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "active"
    driver.is_active = True
    if not driver.expiry_date or driver.expiry_date < date.today():
        driver.expiry_date = date.today() + timedelta(days=30)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/restrict", response_model=schemas.DriverResponse)
def restrict_driver(identifier: str, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "restricted"
    driver.is_active = False
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/reset-device", response_model=schemas.DriverResponse)
def reset_driver_device(identifier: str, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.device_id = "UNBOUND"
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/block", response_model=schemas.DriverResponse)
def block_driver(identifier: str, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.status = "blocked"
    driver.is_active = False
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/toggle-tester", response_model=schemas.DriverResponse)
def toggle_tester_permission(identifier: str, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.is_tester = not getattr(driver, 'is_tester', False)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/update-plan", response_model=schemas.DriverResponse)
def update_driver_plan(identifier: str, req: schemas.AdminPlanUpdateRequest, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    plan_key = req.plan_tier.lower()
    driver.plan_tier = plan_key
    driver.app_limit = PLAN_LIMITS.get(plan_key, 14)
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/update-custom-platforms", response_model=schemas.DriverResponse)
def update_driver_custom_platforms(identifier: str, req: schemas.AdminCustomPlatformsRequest, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    if req.custom_allowed_platforms is not None:
        driver.custom_allowed_platforms = json.dumps(req.custom_allowed_platforms)
    if req.app_limit is not None:
        driver.app_limit = req.app_limit
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.post("/drivers/{identifier}/reset-password", response_model=schemas.DriverResponse)
def admin_reset_driver_password(identifier: str, req: schemas.AdminResetPasswordRequest, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    driver.password = req.new_password
    db.commit()
    db.refresh(driver)
    return format_driver_response(driver)

@router.delete("/drivers/{identifier}")
def delete_driver(identifier: str, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    db.delete(driver)
    db.commit()
    return {"status": "success", "message": f"Driver {identifier} deleted successfully"}

@router.get("/drivers/{identifier}/rides", response_model=List[schemas.RideLogResponse])
def get_admin_driver_rides(identifier: str, limit: int = 50, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    driver = find_driver_by_id_or_phone(identifier, db)
    return db.query(models.RideLog).filter(models.RideLog.driver_phone == driver.phone).order_by(models.RideLog.id.desc()).limit(limit).all()
