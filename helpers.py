import json
from datetime import date
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
import models
import schemas
from auth_utils import generate_tokens_for_driver

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

def check_subscription_validity(driver: models.Driver) -> bool:
    if driver.status != "active":
        return False
    if not driver.expiry_date:
        return False
    return driver.expiry_date >= date.today()

def format_driver_response(
    driver: models.Driver,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None
) -> schemas.DriverResponse:
    is_valid = check_subscription_validity(driver)

    if not access_token or not refresh_token:
        acc_tok, ref_tok = generate_tokens_for_driver(driver.phone, driver.device_id)
        access_token = access_token or acc_tok
        refresh_token = refresh_token or ref_tok

    plan = getattr(driver, 'plan_tier', 'premium') or 'premium'
    limit = getattr(driver, 'app_limit', None)
    if limit is None or limit <= 0:
        limit = PLAN_LIMITS.get(str(plan).lower(), 14)

    raw_custom = getattr(driver, 'custom_allowed_platforms', None)
    custom_list = []
    if raw_custom:
        try:
            parsed = json.loads(raw_custom)
            if isinstance(parsed, list):
                custom_list = parsed
        except Exception:
            custom_list = []

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
        allowed_platforms=custom_list,
        custom_allowed_platforms=custom_list,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        app_version=getattr(driver, 'app_version', None),
        created_at=driver.created_at
    )

def find_driver_by_id_or_phone(identifier: str, db: Session) -> models.Driver:
    clean_id = str(identifier).strip()
    if clean_id.isdigit():
        driver = db.query(models.Driver).filter(models.Driver.id == int(clean_id)).first()
        if driver:
            return driver
    driver = db.query(models.Driver).filter(models.Driver.phone == clean_id).first()
    if driver:
        return driver
    raise HTTPException(status_code=404, detail=f"Driver '{clean_id}' not found.")
