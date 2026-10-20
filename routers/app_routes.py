import os
import glob
import json
import hashlib
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from auth_utils import get_current_admin
from cloudinary_service import upload_apk_raw
from appwrite_service import upload_apk_to_appwrite, is_appwrite_configured

router = APIRouter(prefix="/api/v1/app", tags=["App"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RELEASES_DIR = os.path.join(BASE_DIR, "app_releases")
LATEST_RELEASE_FILE = os.path.join(RELEASES_DIR, "latest_release.json")

DEFAULT_VERSION_NAME = "1.0.4"
DEFAULT_VERSION_CODE = 4
DEFAULT_NOTES = "⚡ Enhanced zero-lag engine, 10ms stealth micro-taps, audio chimes, and eliminated screenshot freeze."

def get_latest_release_from_db(db: Session):
    return db.query(models.AppRelease).order_by(models.AppRelease.version_code.desc(), models.AppRelease.id.desc()).first()

def db_release_to_meta(rel) -> dict:
    return {
        "latest_version": rel.version_name,
        "latest_code": rel.version_code,
        "update_notes": rel.update_notes or f"⚡ AutoRide Update v{rel.version_name}.",
        "force_update": bool(rel.force_update),
        "apk_url": rel.apk_url,
        "size_mb": rel.size_mb or 0,
        "sha256": rel.sha256,
        "uploaded_at": rel.created_at.isoformat() if rel.created_at else None,
    }

def get_latest_release_metadata():
    if os.path.exists(LATEST_RELEASE_FILE):
        try:
            with open(LATEST_RELEASE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[AppRoutes] Error reading latest_release.json:", e)
    return {
        "latest_version": DEFAULT_VERSION_NAME,
        "latest_code": DEFAULT_VERSION_CODE,
        "update_notes": DEFAULT_NOTES,
        "force_update": False,
        "apk_path": None,
        "uploaded_at": None
    }

def save_latest_release_metadata(meta: dict):
    os.makedirs(RELEASES_DIR, exist_ok=True)
    with open(LATEST_RELEASE_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

@router.get("/check-update")
def check_app_update(version_code: int = 1, db: Session = Depends(get_db)):
    rel = get_latest_release_from_db(db)
    meta = db_release_to_meta(rel) if rel else get_latest_release_metadata()
    # Never claim a latest below the baseline, so a stale/empty store can't hide real builds
    latest_code = max(int(meta.get("latest_code", DEFAULT_VERSION_CODE)), DEFAULT_VERSION_CODE)
    latest_version = str(meta.get("latest_version", DEFAULT_VERSION_NAME))
    apk_url = meta.get("apk_url")
    return {
        "latest_version": latest_version,
        "latest_code": latest_code,
        "latest_native_version": latest_version,
        "latest_native_code": latest_code,
        "is_update_available": latest_code > version_code,
        "force_update": bool(meta.get("force_update", False)),
        # Direct Cloudinary URL when hosted, else the server download endpoint
        "apk_download_url": apk_url or "/api/v1/app/download-latest-apk",
        "update_notes": meta.get("update_notes", DEFAULT_NOTES),
        "size_mb": meta.get("size_mb", 23.3)
    }

@router.get("/download-latest-apk")
@router.get("/download-apk")
def download_latest_apk(db: Session = Depends(get_db)):
    rel = get_latest_release_from_db(db)
    if rel and rel.apk_url:
        return RedirectResponse(rel.apk_url)
    meta = get_latest_release_metadata()
    apk_path = meta.get("apk_path")
    if apk_path and os.path.exists(apk_path):
        ver = meta.get("latest_version", DEFAULT_VERSION_NAME)
        return FileResponse(
            apk_path,
            media_type="application/vnd.android.package-archive",
            filename=f"AutoRide-v{ver}.apk"
        )

    # Fallback to search in app_releases folder
    if os.path.exists(RELEASES_DIR):
        apks = glob.glob(os.path.join(RELEASES_DIR, "*", "*.apk"))
        if apks:
            apks.sort(key=os.path.getmtime, reverse=True)
            return FileResponse(
                apks[0],
                media_type="application/vnd.android.package-archive",
                filename=os.path.basename(apks[0])
            )

    # Fallback to mobile gradle output
    gradle_apk = os.path.join(BASE_DIR, "mobile", "android", "app", "build", "outputs", "apk", "release", "app-arm64-v8a-release.apk")
    if os.path.exists(gradle_apk):
        return FileResponse(
            gradle_apk,
            media_type="application/vnd.android.package-archive",
            filename="AutoRide-latest.apk"
        )

    raise HTTPException(status_code=404, detail="No APK build found on server. Please upload an APK first.")

@router.post("/upload-apk")
async def upload_new_apk_build(
    file: UploadFile = File(...),
    version_name: str = Form(...),
    version_code: int = Form(...),
    update_notes: Optional[str] = Form(None),
    force_update: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin)
):
    if not file.filename.lower().endswith(".apk"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only Android package (.apk) files are supported."
        )

    clean_ver = version_name.strip()
    clean_code = int(version_code)
    file_bytes = await file.read()
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size_mb = round(len(file_bytes) / (1024 * 1024), 2)

    # 1. Always archive to local server disk
    today_str = date.today().isoformat()
    rel_folder = os.path.join(RELEASES_DIR, f"{today_str}_v{clean_ver}")
    os.makedirs(rel_folder, exist_ok=True)
    local_apk_path = os.path.join(rel_folder, f"AutoRide-v{clean_ver}.apk")
    with open(local_apk_path, "wb") as f:
        f.write(file_bytes)

    # 2. Try hosting on Appwrite Storage first (50MB+ limit with chunking)
    apk_url = None
    provider = "Server Disk"
    if is_appwrite_configured():
        apk_url = upload_apk_to_appwrite(file_bytes, f"AutoRide-v{clean_ver}.apk")
        if apk_url:
            provider = "Appwrite Storage"

    # Fall back to Cloudinary if Appwrite is not configured
    if not apk_url:
        apk_url = upload_apk_raw(file_bytes, f"autoride_v{clean_ver}_{clean_code}")
        if apk_url:
            provider = "Cloudinary"

    cloud_hosted = bool(apk_url)
    if not apk_url:
        apk_url = "/api/v1/app/download-latest-apk"

    meta = {
        "latest_version": clean_ver,
        "latest_code": clean_code,
        "update_notes": update_notes.strip() if update_notes else f"⚡ AutoRide Update v{clean_ver}.",
        "force_update": bool(force_update),
        "apk_path": local_apk_path,
        "apk_url": apk_url,
        "size_mb": file_size_mb,
        "sha256": sha256_hash,
        "uploaded_at": datetime.utcnow().isoformat()
    }
    save_latest_release_metadata(meta)

    rel = models.AppRelease(
        version_name=clean_ver,
        version_code=clean_code,
        update_notes=update_notes.strip() if update_notes else f"⚡ AutoRide Update v{clean_ver} released.",
        force_update=bool(force_update),
        apk_url=apk_url,
        size_mb=file_size_mb,
        sha256=sha256_hash,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)

    if provider == "Appwrite Storage":
        msg = f"🚀 APK v{clean_ver} (code {clean_code}) hosted on Appwrite Storage Bucket!"
    elif provider == "Cloudinary":
        msg = f"APK v{clean_ver} (code {clean_code}) hosted on Cloudinary!"
    else:
        msg = f"APK v{clean_ver} saved locally! Cloudinary Free tier caps raw files at 10MB ({file_size_mb}MB uploaded). Set APPWRITE_BUCKET_ID in backend/.env for free cloud hosting, or use 'Register by URL' with GitHub Releases."

    return {
        "status": "success",
        "message": msg,
        "provider": provider,
        "cloud_hosted": cloud_hosted,
        "release": db_release_to_meta(rel)
    }

@router.post("/releases/register")
def register_release_by_url(
    version_name: str = Form(...),
    version_code: int = Form(...),
    apk_url: str = Form(...),
    update_notes: Optional[str] = Form(None),
    force_update: Optional[bool] = Form(False),
    size_mb: Optional[float] = Form(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin)
):
    """Registers a release that is already hosted somewhere (GitHub release, Drive, S3, etc.).
    No upload needed; drivers download straight from apk_url. Use when Cloudinary isn't configured."""
    url = apk_url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="apk_url must be a full https link to the .apk file.")
    rel = models.AppRelease(
        version_name=version_name.strip(),
        version_code=int(version_code),
        update_notes=update_notes.strip() if update_notes else f"⚡ AutoRide Update v{version_name.strip()}.",
        force_update=bool(force_update),
        apk_url=url,
        size_mb=size_mb,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return {"status": "success", "message": f"Release v{rel.version_name} (code {rel.version_code}) registered.", "release": db_release_to_meta(rel)}

@router.get("/releases")
def list_available_releases(db: Session = Depends(get_db)):
    db_rows = get_latest_release_from_db(db)
    db_releases = [db_release_to_meta(r) for r in db.query(models.AppRelease).order_by(models.AppRelease.version_code.desc()).limit(20).all()]
    meta = db_release_to_meta(db_rows) if db_rows else get_latest_release_metadata()
    releases = []
    if os.path.exists(RELEASES_DIR):
        for entry in os.listdir(RELEASES_DIR):
            entry_path = os.path.join(RELEASES_DIR, entry)
            if os.path.isdir(entry_path):
                files = os.listdir(entry_path)
                releases.append({
                    "folder": entry,
                    "files": files,
                    "date": entry.split("_")[0] if "_" in entry else None
                })
    return {
        "latest_version": meta.get("latest_version", DEFAULT_VERSION_NAME),
        "latest_code": meta.get("latest_code", DEFAULT_VERSION_CODE),
        "update_notes": meta.get("update_notes", DEFAULT_NOTES),
        "db_releases": db_releases,
        "releases": releases
    }

PRICING_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pricing_plans.json")

def get_pricing_plans():
    if os.path.exists(PRICING_FILE):
        try:
            with open(PRICING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[AppRoutes] Error reading pricing_plans.json:", e)
    return [
        {"id": "trial", "name": "1-Day Trial", "tagline": "Test on the road today", "price": 30, "currency": "₹", "period": "/ day", "featured": False, "badge": "STARTER", "features": ["10ms Auto-Accept Engine", "All 10+ Supported Platforms", "Min Fare & Max Distance Rules", "Anti-Ban Stealth Touch Jitter"], "cta_text": "Start 1-Day Trial", "cta_link": "/api/v1/app/download-latest-apk"},
        {"id": "weekly", "name": "7-Day Weekly Pass", "tagline": "For regular full-time drivers", "price": 199, "currency": "₹", "period": "/ week", "featured": True, "badge": "MOST POPULAR", "features": ["All Features Included", "Anti-Bot Stealth Jitter", "Multi-Platform Priority", "WhatsApp Priority Support"], "cta_text": "Get Weekly Pass", "cta_link": "/api/v1/app/download-latest-apk"},
        {"id": "monthly", "name": "30-Day Monthly Pro", "tagline": "Maximum savings for pros", "price": 399, "currency": "₹", "period": "/ month", "featured": False, "badge": "BEST VALUE", "features": ["30-Day Unlimited Access", "Free Device Hardware Unbind", "VIP Telegram Helpline", "Highest Daily Extra Earnings"], "cta_text": "Get Monthly Pro", "cta_link": "/api/v1/app/download-latest-apk"}
    ]

@router.get("/pricing-plans")
def list_pricing_plans():
    return {
        "status": "success",
        "plans": get_pricing_plans()
    }

@router.post("/pricing-plans")
def update_pricing_plans(plans: list, _: dict = Depends(get_current_admin)):
    with open(PRICING_FILE, "w", encoding="utf-8") as f:
        json.dump(plans, f, indent=2)
    return {
        "status": "success",
        "message": "Pricing plans updated successfully",
        "plans": plans
    }

