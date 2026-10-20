import os
import io
import base64
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_cloudinary_initialized = False

def init_cloudinary():
    global _cloudinary_initialized
    if _cloudinary_initialized:
        return
    try:
        import cloudinary
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        api_key = os.getenv("CLOUDINARY_API_KEY")
        api_secret = os.getenv("CLOUDINARY_API_SECRET")
        cloudinary_url = os.getenv("CLOUDINARY_URL")

        if cloudinary_url:
            cloudinary.config()
            _cloudinary_initialized = True
        elif cloud_name and api_key and api_secret:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )
            _cloudinary_initialized = True
    except Exception as e:
        print("[Cloudinary] Config error:", e)

def upload_screenshot_image(image_data: bytes, public_name: str) -> Optional[str]:
    """
    Uploads raw image bytes to Cloudinary.
    Falls back to saving locally in backend/static/screenshots if Cloudinary is not configured.
    """
    init_cloudinary()
    
    # 1. Try Cloudinary upload
    try:
        import cloudinary
        import cloudinary.uploader
        
        # Check if configured
        if _cloudinary_initialized:
            result = cloudinary.uploader.upload(
                io.BytesIO(image_data),
                folder="autoride_screenshots",
                public_id=public_name,
                resource_type="image",
                format="webp",
                tags=["autoride", "ride_proof"]
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return secure_url
    except Exception as e:
        print(f"[Cloudinary] Remote upload failed, falling back to local: {e}")

    # 2. Local fallback storage
    try:
        static_dir = os.path.join(os.path.dirname(__file__), "static", "screenshots")
        os.makedirs(static_dir, exist_ok=True)
        file_path = os.path.join(static_dir, f"{public_name}.jpg")
        with open(file_path, "wb") as f:
            f.write(image_data)
        return f"/static/screenshots/{public_name}.jpg"
    except Exception as e:
        print(f"[Storage] Local fallback failed: {e}")
        return None

def upload_apk_raw(apk_bytes: bytes, public_name: str) -> Optional[str]:
    """Uploads an APK to Cloudinary as a raw file and returns its download URL.
    APKs must persist across deploys, so there is no local-disk fallback (Render wipes it)."""
    init_cloudinary()
    if not _cloudinary_initialized:
        return None
    try:
        import cloudinary
        import cloudinary.uploader
        result = cloudinary.uploader.upload_large(
            io.BytesIO(apk_bytes),
            folder="autoride_apks",
            public_id=public_name,
            resource_type="raw",
            overwrite=True,
            tags=["autoride", "apk"]
        ) if len(apk_bytes) > 20 * 1024 * 1024 else cloudinary.uploader.upload(
            io.BytesIO(apk_bytes),
            folder="autoride_apks",
            public_id=public_name,
            resource_type="raw",
            overwrite=True,
            tags=["autoride", "apk"]
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"[Cloudinary] APK upload failed: {e}")
        return None


def process_and_upload_screenshot(
    image_bytes: Optional[bytes] = None,
    image_base64: Optional[str] = None,
    filename_prefix: str = "ride"
) -> Optional[str]:
    """
    Accepts either raw bytes or base64 string, decodes, and uploads to Cloudinary.
    """
    data = None
    if image_bytes and len(image_bytes) > 0:
        data = image_bytes
    elif image_base64 and len(image_base64.strip()) > 0:
        clean_b64 = image_base64.strip()
        if "base64," in clean_b64:
            clean_b64 = clean_b64.split("base64,")[1]
        try:
            data = base64.b64decode(clean_b64)
        except Exception as e:
            print("[Storage] Base64 decode error:", e)
            return None

    if not data:
        return None

    import time
    clean_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ("_", "-"))
    public_id = f"{clean_prefix}_{int(time.time() * 1000)}"
    return upload_screenshot_image(data, public_id)
