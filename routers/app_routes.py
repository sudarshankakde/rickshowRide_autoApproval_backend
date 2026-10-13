import os
import glob
import json
import hashlib
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.responses import FileResponse
from auth_utils import get_current_admin

router = APIRouter(prefix="/api/v1/app", tags=["App"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RELEASES_DIR = os.path.join(BASE_DIR, "app_releases")
LATEST_RELEASE_FILE = os.path.join(RELEASES_DIR, "latest_release.json")

DEFAULT_VERSION_NAME = "1.0.3"
DEFAULT_VERSION_CODE = 3
DEFAULT_NOTES = "⚡ Enhanced zero-lag engine, 10ms stealth micro-taps, audio chimes, and eliminated screenshot freeze."

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
def check_app_update(version_code: int = 1):
    meta = get_latest_release_metadata()
    latest_code = int(meta.get("latest_code", DEFAULT_VERSION_CODE))
    latest_version = str(meta.get("latest_version", DEFAULT_VERSION_NAME))
    is_update_available = latest_code > version_code
    return {
        "latest_native_version": latest_version,
        "latest_native_code": latest_code,
        "is_update_available": is_update_available,
        "force_update": bool(meta.get("force_update", False)),
        "apk_download_url": "/api/v1/app/download-latest-apk",
        "update_notes": meta.get("update_notes", DEFAULT_NOTES)
    }

@router.get("/download-latest-apk")
def download_latest_apk():
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
    _: dict = Depends(get_current_admin)
):
    if not file.filename.lower().endswith(".apk"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only Android package (.apk) files are supported."
        )

    clean_ver = version_name.strip()
    clean_code = int(version_code)
    today_str = date.today().isoformat()
    dest_dir = os.path.join(RELEASES_DIR, f"{today_str}_v{clean_ver}")
    os.makedirs(dest_dir, exist_ok=True)

    dest_file = os.path.join(dest_dir, "app-release.apk")
    file_bytes = await file.read()

    with open(dest_file, "wb") as f:
        f.write(file_bytes)

    # Compute SHA-256
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size_mb = round(len(file_bytes) / (1024 * 1024), 2)

    # Save metadata
    meta = {
        "latest_version": clean_ver,
        "latest_code": clean_code,
        "update_notes": update_notes.strip() if update_notes else f"⚡ AutoRide Update v{clean_ver} released.",
        "force_update": bool(force_update),
        "apk_path": dest_file,
        "filename": file.filename,
        "sha256": sha256_hash,
        "size_mb": file_size_mb,
        "uploaded_at": datetime.now().isoformat()
    }
    save_latest_release_metadata(meta)

    # Also update workspace root app-arm64-release.apk for quick access
    root_apk = os.path.join(BASE_DIR, "app-arm64-release.apk")
    try:
        with open(root_apk, "wb") as f:
            f.write(file_bytes)
    except Exception:
        pass

    return {
        "status": "success",
        "message": f"APK v{clean_ver} (code {clean_code}) uploaded successfully!",
        "release": meta
    }

@router.get("/releases")
def list_available_releases():
    meta = get_latest_release_metadata()
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
        "releases": releases
    }
