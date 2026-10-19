from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_tests():
    print("Testing Backend Endpoints with Secure Admin Auth & TestClient...")

    # 1. Health check
    res = client.get("/")
    print(f"[1] Root Status: {res.status_code} -> {res.json()}")
    assert res.status_code == 200

    # 2. Driver Registration
    reg_payload = {
        "name": "Ramesh Auto Driver",
        "phone": "9876543210",
        "device_id": "test_device_abc123",
        "password": "driverSecret123"
    }
    res = client.post("/api/v1/drivers/register", json=reg_payload)
    data = res.json()
    print(f"[2] Register Status: {res.status_code} -> Phone: {data.get('phone')}")
    assert res.status_code == 200

    # 3. Check Driver Status
    res = client.get("/api/v1/drivers/status?phone=9876543210&device_id=test_device_abc123")
    print(f"[3] Check Status: {res.status_code} -> Status: {res.json().get('status')}")
    assert res.status_code == 200

    # 4. Verify Admin Route is Protected (Unauthenticated should 401)
    res = client.get("/api/v1/admin/drivers")
    print(f"[4] Unauthenticated Admin Check: {res.status_code} -> {res.json().get('detail')}")
    assert res.status_code == 401

    # 5. Admin Login to acquire JWT Bearer token
    login_payload = {"username": "sudarshan", "password": "Qweasdzx@1#"}
    res = client.post("/api/v1/admin/login", json=login_payload)
    login_data = res.json()
    print(f"[5] Admin Login: {res.status_code} -> Role: {login_data.get('role')}, Token: {bool(login_data.get('token'))}")
    assert res.status_code == 200
    admin_token = login_data.get("token")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 6. Admin Approves Driver using Bearer token
    approve_payload = {"expiry_days": 30}
    res = client.post("/api/v1/admin/drivers/9876543210/approve", json=approve_payload, headers=headers)
    print(f"[6] Admin Approve Status: {res.status_code} -> Expiry: {res.json().get('expiry_date')}")
    assert res.status_code == 200

    # 7. Ride Logging with Active v1.0.3 Telemetry
    ride_payload = {
        "driver_phone": "9876543210",
        "platform": "Rapido",
        "fare": 180,
        "status": "accepted",
        "reason": "Micro-tap accepted within fare bounds",
        "app_version": "1.0.3",
        "system_min_fare": 100,
        "system_max_fare": 1500
    }
    ride_payload["client_ride_id"] = "test-ride-0001"
    ride_payload["latency_ms"] = 140
    res = client.post("/api/v1/rides/log", json=ride_payload)
    print(f"[7] Ride Log Telemetry: {res.status_code} -> Fare: {res.json().get('fare')}, Version: {res.json().get('app_version')}")
    assert res.status_code == 200
    assert res.json().get("latency_ms") == 140

    # 7b. Post-accept verification result attaches to the logged ride
    verify_payload = {"driver_phone": "9876543210", "client_ride_id": "test-ride-0001",
                      "verified_status": "Accepted", "verified_reason": "Trip screen confirmed"}
    res = client.post("/api/v1/rides/verify", json=verify_payload)
    print(f"[7b] Ride Verify: {res.status_code} -> {res.json().get('verified_status')}")
    assert res.status_code == 200 and res.json().get("verified_status") == "Accepted"
    res = client.post("/api/v1/rides/verify", json={**verify_payload, "client_ride_id": "missing"})
    assert res.status_code == 404

    # 7c. Engine heartbeat
    res = client.post("/api/v1/drivers/heartbeat", json={"driver_phone": "9876543210", "engine_connected": True,
                                                          "is_active": True, "last_event_age_ms": 1200, "error_count": 0})
    print(f"[7c] Heartbeat: {res.status_code} -> {res.json()}")
    assert res.status_code == 200

    # 7d. Failure screen dump ingest + admin health views
    dump_payload = {"driver_phone": "9876543210", "platform": "Uber", "kind": "Click Failed",
                    "client_ride_id": "test-ride-0001", "screen_text": "Match | ₹220 | 3 min",
                    "nodes_json": "[{\"t\": \"Match\", \"k\": true}]", "screen_width": 1080, "screen_height": 2400}
    res = client.post("/api/v1/rides/screen-dump", json=dump_payload)
    print(f"[7d] Screen Dump: {res.status_code} -> {res.json()}")
    assert res.status_code == 200 and res.json().get("status") == "ok"
    assert client.post("/api/v1/rides/screen-dump", json={**dump_payload, "driver_phone": "0000000000"}).status_code == 404

    # 8. Admin Stats & Telemetry (Verify v1.0.3 adoption)
    res = client.get("/api/v1/admin/engine-health", headers=headers)
    me = [d for d in res.json() if d["phone"] == "9876543210"][0]
    print(f"[7e] Engine Health: {res.status_code} -> stale={me['stale']}, engine={me['engine']}")
    assert res.status_code == 200 and me["stale"] is False and me["engine"]["is_active"] is True
    res = client.get("/api/v1/admin/accept-quality?days=1", headers=headers)
    rapido = [p for p in res.json() if p["platform"] == "Rapido"][0]
    print(f"[7f] Accept Quality: {res.status_code} -> {rapido}")
    assert res.status_code == 200 and rapido["outcomes"].get("Accepted", 0) >= 1
    res = client.get("/api/v1/admin/screen-dumps?platform=Uber", headers=headers)
    assert res.status_code == 200 and len(res.json()) >= 1
    res = client.get(f"/api/v1/admin/screen-dumps/{res.json()[0]['id']}", headers=headers)
    assert res.status_code == 200 and "Match" in res.json()["screen_text"]
    assert client.get("/api/v1/admin/engine-health").status_code == 401

    res = client.get("/api/v1/admin/stats", headers=headers)
    stats = res.json()
    print(f"[8] Admin Stats: {res.status_code} -> v1.0.3 Count: {stats.get('latest_adoption_count')}, Adoption: {stats.get('latest_adoption_percentage')}%")
    assert res.status_code == 200

    # 9. Driver Login & Token Generation
    driver_login_payload = {
        "phone": "9876543210",
        "password": "driverSecret123",
        "device_id": "test_device_abc123"
    }
    res = client.post("/api/v1/drivers/login", json=driver_login_payload)
    print(f"[9] Driver Login: {res.status_code} -> Access Token: {bool(res.json().get('access_token'))}")
    assert res.status_code == 200
    refresh_token = res.json().get("refresh_token")

    # 10. Driver Token Refresh
    res = client.post("/api/v1/drivers/refresh-token", json={"refresh_token": refresh_token})
    print(f"[10] Token Refresh: {res.status_code} -> New Access Token: {bool(res.json().get('access_token'))}")
    assert res.status_code == 200

    # 11. Live Rides Stream
    res = client.get("/api/v1/admin/live-rides", headers=headers)
    print(f"[11] Live Rides Stream: {res.status_code} -> Count: {len(res.json())}")
    assert res.status_code == 200

    # 12. Driver Specific Rides Telemetry (for Driver Profile Modal)
    res = client.get("/api/v1/admin/drivers/9876543210/rides", headers=headers)
    print(f"[12] Driver Rides History: {res.status_code} -> Rides Count: {len(res.json())}")
    assert res.status_code == 200

    # 13. App Release Catalog
    res = client.get("/api/v1/app/releases")
    print(f"[13] App Releases: {res.status_code} -> Latest: {res.json().get('latest_version')}")
    assert res.status_code == 200

    print("\n[SUCCESS] All 12 Backend Endpoints, Auth & Telemetry Tests Passed!")

if __name__ == "__main__":
    run_tests()
