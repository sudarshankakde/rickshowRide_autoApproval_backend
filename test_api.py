import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def make_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    body = json.dumps(data).encode('utf-8') if data else None
    try:
        with urllib.request.urlopen(req, data=body) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error_raw": raw}


def run_tests():
    print("Testing Backend Endpoints...")
    time.sleep(2) # wait for uvicorn startup

    # 1. Health check
    status, res = make_request(f"{BASE_URL}/")
    print(f"[1] Root Status: {status} -> {res}")

    # 2. Driver Registration
    reg_payload = {
        "name": "Ramesh Auto Driver",
        "phone": "9876543210",
        "device_id": "test_device_abc123"
    }
    status, res = make_request(f"{BASE_URL}/api/v1/drivers/register", method="POST", data=reg_payload)
    print(f"[2] Register Status: {status} -> Status: {res.get('status')}, Phone: {res.get('phone')}")

    # 3. Check Driver Status (should be pending)
    status, res = make_request(f"{BASE_URL}/api/v1/drivers/status?phone=9876543210&device_id=test_device_abc123")
    print(f"[3] Check Status: {status} -> Status: {res.get('status')}, Valid Subscription: {res.get('is_valid_subscription')}")

    # 4. Admin Approves Driver
    approve_payload = {"expiry_days": 30}
    status, res = make_request(f"{BASE_URL}/api/v1/admin/drivers/9876543210/approve", method="POST", data=approve_payload)
    print(f"[4] Admin Approve Status: {status} -> New Status: {res.get('status')}, Expiry: {res.get('expiry_date')}, Valid Subscription: {res.get('is_valid_subscription')}")

    # 5. Driver Update Settings
    settings_payload = {
        "phone": "9876543210",
        "device_id": "test_device_abc123",
        "min_fare": 150,
        "max_fare": 2000,
        "is_active": True
    }
    status, res = make_request(f"{BASE_URL}/api/v1/drivers/settings", method="PUT", data=settings_payload)
    print(f"[5] Update Settings Status: {status} -> Min Fare: {res.get('min_fare')}, Max Fare: {res.get('max_fare')}")

    print("\n[SUCCESS] All Backend API Tests Completed Successfully!")


if __name__ == "__main__":
    run_tests()
