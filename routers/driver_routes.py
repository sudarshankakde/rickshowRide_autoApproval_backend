from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from helpers import format_driver_response
from auth_utils import (
    generate_tokens_for_driver,
    decode_jwt_token,
    verify_password,
    hash_password
)

router = APIRouter(prefix="/api/v1/drivers", tags=["Drivers"])

@router.post("/register", response_model=schemas.DriverResponse)
def register_driver(req: schemas.DriverRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.Driver).filter(models.Driver.phone == req.phone).first()
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

    new_driver = models.Driver(
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
        is_active=True,
        custom_allowed_platforms="[]"
    )
    db.add(new_driver)
    db.commit()
    db.refresh(new_driver)
    acc_tok, ref_tok = generate_tokens_for_driver(new_driver.phone, new_driver.device_id)
    return format_driver_response(new_driver, acc_tok, ref_tok)

@router.post("/login", response_model=schemas.DriverResponse)
def login_driver(req: schemas.DriverLoginRequest, db: Session = Depends(get_db)):
    driver = db.query(models.Driver).filter(models.Driver.phone == req.phone).first()
    if not driver:
        raise HTTPException(
            status_code=404, 
            detail="Account not found. No registered user with this phone number. Please register first."
        )
    
    if driver.password and not verify_password(req.password, driver.password):
        raise HTTPException(
            status_code=401, 
            detail="Incorrect password. Please verify your mobile number and password."
        )

    # Seamless upgrade from plaintext to bcrypt hash upon successful login
    if driver.password and not driver.password.startswith("$2b$"):
        try:
            driver.password = hash_password(req.password)
        except Exception:
            pass

    # Update bound device ID on login
    driver.device_id = req.device_id
    db.commit()
    db.refresh(driver)

    acc_tok, ref_tok = generate_tokens_for_driver(driver.phone, driver.device_id)
    return format_driver_response(driver, acc_tok, ref_tok)

@router.post("/refresh-token", response_model=schemas.TokenResponse)
def refresh_access_token(req: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_jwt_token(req.refresh_token)
        phone = payload.get("sub")
        device_id = payload.get("device_id")
        token_type = payload.get("type")

        if not phone or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token format.")

        driver = db.query(models.Driver).filter(models.Driver.phone == phone).first()
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

@router.get("/status", response_model=schemas.DriverResponse)
def get_driver_status(phone: str, device_id: str, db: Session = Depends(get_db)):
    driver = db.query(models.Driver).filter(models.Driver.phone == phone).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    return format_driver_response(driver)

@router.put("/settings", response_model=schemas.DriverResponse)
def update_settings(req: schemas.DriverSettingsUpdate, db: Session = Depends(get_db)):
    driver = db.query(models.Driver).filter(models.Driver.phone == req.phone).first()
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
