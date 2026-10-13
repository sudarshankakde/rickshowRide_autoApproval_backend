import os
import hmac
import hashlib
import base64
import json
import time
from typing import Optional
import bcrypt
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from database import get_db
import models

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "autoride_super_secret_jwt_key_pilot_drive_2026")
ACCESS_TOKEN_EXPIRE_SECONDS = 86400 * 7   # 7 days
REFRESH_TOKEN_EXPIRE_SECONDS = 86400 * 30 # 30 days
SUPERADMIN_TOKEN = os.getenv("SUPERADMIN_TOKEN", "AUTORIDE_SUPERADMIN_SESSION_TOKEN_SECURE_2026")

def hash_password(password: str) -> str:
    """Hash password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_or_plain: Optional[str]) -> bool:
    """Verify password against bcrypt hash, with fallback to legacy plaintext."""
    if not hashed_or_plain:
        return True
    if hashed_or_plain.startswith("$2b$") or hashed_or_plain.startswith("$2a$"):
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_or_plain.encode('utf-8'))
        except Exception:
            return False
    return plain_password == hashed_or_plain

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def create_jwt_token(payload: dict, expires_in: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + expires_in
    payload_copy["iat"] = int(time.time())

    encoded_header = base64url_encode(json.dumps(header).encode('utf-8'))
    encoded_payload = base64url_encode(json.dumps(payload_copy).encode('utf-8'))

    signature_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), signature_input, hashlib.sha256).digest()
    encoded_signature = base64url_encode(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

def decode_jwt_token(token: str) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    
    encoded_header, encoded_payload, encoded_signature = parts
    signature_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
    expected_signature = base64url_encode(hmac.new(SECRET_KEY.encode('utf-8'), signature_input, hashlib.sha256).digest())

    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise ValueError("Invalid token signature")

    payload = json.loads(base64url_decode(encoded_payload).decode('utf-8'))
    if payload.get("exp") and payload["exp"] < time.time():
        raise ValueError("Token has expired")

    return payload

def generate_tokens_for_driver(phone: str, device_id: str):
    access_token = create_jwt_token({"sub": phone, "device_id": device_id, "role": "driver", "type": "access"}, ACCESS_TOKEN_EXPIRE_SECONDS)
    refresh_token = create_jwt_token({"sub": phone, "device_id": device_id, "role": "driver", "type": "refresh"}, REFRESH_TOKEN_EXPIRE_SECONDS)
    return access_token, refresh_token

def create_admin_token(username: str, role: str = "superadmin", expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS) -> str:
    return create_jwt_token({"sub": username, "role": role, "type": "access"}, expires_in)

def extract_token_from_header(authorization: Optional[str], x_admin_token: Optional[str]) -> Optional[str]:
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        elif len(parts) == 1:
            return parts[0]
    if x_admin_token:
        return x_admin_token.strip()
    return None

def get_current_admin(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    token = extract_token_from_header(authorization, x_admin_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required. Missing Bearer token in Authorization header."
        )

    # Legacy static token fallback for backward compatibility
    if token == SUPERADMIN_TOKEN:
        return {"username": "superadmin", "role": "superadmin", "source": "static_key"}

    try:
        payload = decode_jwt_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired admin token: {str(e)}"
        )

    role = payload.get("role")
    username = payload.get("sub")
    if role not in ("superadmin", "admin") or not username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin privileges required."
        )

    # Verify admin in DB if table exists
    try:
        admin = db.query(models.Admin).filter(models.Admin.username == username, models.Admin.is_active == True).first()
        if admin:
            return {"username": admin.username, "role": admin.role, "id": admin.id}
    except Exception:
        pass

    return {"username": username, "role": role, "source": "jwt"}

