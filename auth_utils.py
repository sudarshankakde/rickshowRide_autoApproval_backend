import hmac
import hashlib
import base64
import json
import time

SECRET_KEY = "autoride_super_secret_jwt_key_pilot_drive_2026"
ACCESS_TOKEN_EXPIRE_SECONDS = 86400 * 7   # 7 days
REFRESH_TOKEN_EXPIRE_SECONDS = 86400 * 30 # 30 days

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
    access_token = create_jwt_token({"sub": phone, "device_id": device_id, "type": "access"}, ACCESS_TOKEN_EXPIRE_SECONDS)
    refresh_token = create_jwt_token({"sub": phone, "device_id": device_id, "type": "refresh"}, REFRESH_TOKEN_EXPIRE_SECONDS)
    return access_token, refresh_token
