import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from helpers import check_subscription_validity
from cloudinary_service import process_and_upload_screenshot

router = APIRouter(tags=["Rides"])

@router.post("/api/v1/rides/log", response_model=schemas.RideLogResponse)
@router.post("/api/v1/rides/log/", response_model=schemas.RideLogResponse)
@router.post("/api/v1/drivers/rides/log", response_model=schemas.RideLogResponse)
@router.post("/api/v1/drivers/rides/log/", response_model=schemas.RideLogResponse)
def log_ride_offer(req: schemas.RideLogCreate, db: Session = Depends(get_db)):
    screenshot_url = req.screenshot_url
    if not screenshot_url and req.image_base64:
        screenshot_url = process_and_upload_screenshot(
            image_base64=req.image_base64,
            filename_prefix=f"{req.driver_phone}_{req.platform}_{req.status}"
        )

    ride = models.RideLog(
        driver_phone=req.driver_phone,
        platform=req.platform,
        fare=req.fare,
        pickup=req.pickup,
        drop=req.drop,
        distance=req.distance,
        status=req.status,
        reason=req.reason,
        screenshot_url=screenshot_url,
        system_min_fare=req.system_min_fare,
        system_max_fare=req.system_max_fare,
        system_max_distance=req.system_max_distance,
        app_version=req.app_version,
        client_ride_id=req.client_ride_id,
        latency_ms=req.latency_ms
    )
    db.add(ride)

    # Automatically update telemetry app_version on driver profile
    if req.app_version:
        driver = db.query(models.Driver).filter(models.Driver.phone == req.driver_phone).first()
        if driver:
            driver.app_version = req.app_version

    db.commit()
    db.refresh(ride)
    return ride

@router.post("/api/v1/rides/log-screenshot", response_model=schemas.RideLogResponse)
@router.post("/api/v1/rides/log-screenshot/", response_model=schemas.RideLogResponse)
@router.post("/api/v1/drivers/rides/log-screenshot", response_model=schemas.RideLogResponse)
@router.post("/api/v1/drivers/rides/log-screenshot/", response_model=schemas.RideLogResponse)
async def log_ride_offer_with_screenshot(
    driver_phone: str = Form(...),
    platform: str = Form(...),
    fare: int = Form(...),
    status: str = Form(...),
    distance: Optional[float] = Form(None),
    pickup: Optional[str] = Form(None),
    drop: Optional[str] = Form(None),
    reason: Optional[str] = Form(None),
    system_min_fare: Optional[int] = Form(None),
    system_max_fare: Optional[int] = Form(None),
    system_max_distance: Optional[float] = Form(None),
    app_version: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    screenshot_url = None
    if file:
        file_bytes = await file.read()
        screenshot_url = process_and_upload_screenshot(
            image_bytes=file_bytes,
            filename_prefix=f"{driver_phone}_{platform}_{status}"
        )

    ride = models.RideLog(
        driver_phone=driver_phone,
        platform=platform,
        fare=fare,
        pickup=pickup,
        drop=drop,
        distance=distance,
        status=status,
        reason=reason,
        screenshot_url=screenshot_url,
        system_min_fare=system_min_fare,
        system_max_fare=system_max_fare,
        system_max_distance=system_max_distance,
        app_version=app_version
    )
    db.add(ride)
    if app_version:
        driver = db.query(models.Driver).filter(models.Driver.phone == driver_phone).first()
        if driver:
            driver.app_version = app_version
    db.commit()
    db.refresh(ride)
    return ride

@router.get("/api/v1/rides/history", response_model=List[schemas.RideLogResponse])
@router.get("/api/v1/rides/history/", response_model=List[schemas.RideLogResponse])
@router.get("/api/v1/drivers/rides/history", response_model=List[schemas.RideLogResponse])
@router.get("/api/v1/drivers/rides/history/", response_model=List[schemas.RideLogResponse])
def get_ride_history(phone: str, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(models.RideLog).filter(models.RideLog.driver_phone == phone).order_by(models.RideLog.id.desc()).limit(limit).all()

@router.post("/api/v1/rides/verify", response_model=schemas.RideLogResponse)
@router.post("/api/v1/drivers/rides/verify", response_model=schemas.RideLogResponse)
def verify_ride(req: schemas.RideVerifyRequest, db: Session = Depends(get_db)):
    """Attaches the app's post-accept verification result to the ride it logged earlier."""
    ride = (
        db.query(models.RideLog)
        .filter(models.RideLog.driver_phone == req.driver_phone, models.RideLog.client_ride_id == req.client_ride_id)
        .order_by(models.RideLog.id.desc())
        .first()
    )
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    ride.verified_status = req.verified_status[:30]
    ride.verified_reason = (req.verified_reason or "")[:255] or None
    db.commit()
    db.refresh(ride)
    return ride

@router.post("/api/v1/drivers/heartbeat")
def driver_heartbeat(req: schemas.DriverHeartbeatRequest, db: Session = Depends(get_db)):
    """Engine liveness ping, sent every few minutes while the accessibility engine is running."""
    driver = db.query(models.Driver).filter(models.Driver.phone == req.driver_phone).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    driver.last_heartbeat_at = datetime.now(timezone.utc)
    driver.engine_status = json.dumps(req.model_dump(exclude={"driver_phone"}))[:500]
    if req.app_version:
        driver.app_version = req.app_version
    db.commit()
    return {
        "status": "ok",
        "driver_status": driver.status,
        "is_valid_subscription": check_subscription_validity(driver),
        "expiry_date": driver.expiry_date.isoformat() if driver.expiry_date else None,
    }
