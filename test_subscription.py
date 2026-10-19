"""Subscription lifecycle checks: plan limits, expiry (IST), restrict/block, and token refresh.

Run against a throwaway database, e.g. DATABASE_URL=sqlite:///./tmp_test.db python test_subscription.py
"""
from datetime import timedelta
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
import models
from helpers import business_today

client = TestClient(app)
PHONE = "9000000001"


def admin_headers():
    res = client.post("/api/v1/admin/login", json={"username": "sudarshan", "password": "Qweasdzx@1#"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


def status():
    return client.get(f"/api/v1/drivers/status?phone={PHONE}&device_id=dev1").json()


def set_expiry(days_from_today):
    db = SessionLocal()
    d = db.query(models.Driver).filter(models.Driver.phone == PHONE).first()
    d.expiry_date = business_today() + timedelta(days=days_from_today)
    db.commit()
    db.close()


def run():
    h = admin_headers()
    reg = client.post("/api/v1/drivers/register", json={"name": "Sub Test", "phone": PHONE, "device_id": "dev1", "password": "pw123456"})
    assert reg.status_code == 200, reg.text
    assert status()["is_valid_subscription"] is False, "pending driver must not be valid"

    assert client.post(f"/api/v1/admin/drivers/{PHONE}/approve", json={"expiry_days": 30}, headers=h).status_code == 200
    s = status()
    assert s["status"] == "active" and s["is_valid_subscription"] is True
    print("[1] approve -> active & valid")

    for tier, limit in (("basic", 4), ("standard", 9), ("premium", 14)):
        res = client.post(f"/api/v1/admin/drivers/{PHONE}/update-plan", json={"plan_tier": tier}, headers=h)
        assert res.status_code == 200, res.text
        assert status()["app_limit"] == limit, (tier, status()["app_limit"])
    print("[2] plan tiers -> app_limit 4 / 9 / 14")

    set_expiry(0)
    assert status()["is_valid_subscription"] is True, "plan is valid through its last day (IST)"
    set_expiry(-1)
    assert status()["is_valid_subscription"] is False, "expired yesterday (IST) must be invalid"
    hb = client.post("/api/v1/drivers/heartbeat", json={"driver_phone": PHONE}).json()
    assert hb["is_valid_subscription"] is False, "heartbeat must report expiry to the engine"
    print("[3] expiry boundary in IST + heartbeat reports it")

    set_expiry(10)
    assert client.post(f"/api/v1/admin/drivers/{PHONE}/restrict", headers=h).status_code == 200
    assert status()["is_valid_subscription"] is False
    assert client.post(f"/api/v1/admin/drivers/{PHONE}/unrestrict", headers=h).status_code == 200
    assert status()["is_valid_subscription"] is True
    print("[4] restrict / unrestrict")

    login = client.post("/api/v1/drivers/login", json={"phone": PHONE, "password": "pw123456", "device_id": "dev1"}).json()
    assert client.post(f"/api/v1/admin/drivers/{PHONE}/block", headers=h).status_code == 200
    s = status()
    assert s["is_valid_subscription"] is False and s["is_active"] is False
    refresh = client.post("/api/v1/drivers/refresh-token", json={"refresh_token": login["refresh_token"]})
    assert refresh.status_code == 403, refresh.text
    print("[5] block -> invalid, engine paused, token refresh refused")

    full = client.put(f"/api/v1/admin/drivers/{PHONE}", json={
        "name": "Renamed Driver", "city": "Mumbai", "status": "active", "expiry_days": 45,
        "plan_tier": "basic", "min_fare": 60, "max_fare": 900, "max_distance": 7.5,
        "is_tester": True, "reset_device": True, "new_password": "fresh123",
    }, headers=h)
    assert full.status_code == 200, full.text
    b = full.json()
    assert b["name"] == "Renamed Driver" and b["city"] == "Mumbai"
    assert b["plan_tier"] == "basic" and b["app_limit"] == 4
    assert b["min_fare"] == 60 and b["max_fare"] == 900 and b["max_distance"] == 7.5
    assert b["is_tester"] is True and b["device_id"] == "UNBOUND"
    assert b["is_valid_subscription"] is True and not b.get("access_token")
    assert client.post("/api/v1/drivers/login", json={"phone": PHONE, "password": "fresh123", "device_id": "d2"}).status_code == 200
    assert client.post("/api/v1/drivers/login", json={"phone": PHONE, "password": "pw123456", "device_id": "d2"}).status_code == 401
    assert client.put(f"/api/v1/admin/drivers/{PHONE}", json={"status": "wizard"}, headers=h).status_code == 422
    assert client.put(f"/api/v1/admin/drivers/{PHONE}", json={"min_fare": 500, "max_fare": 100}, headers=h).status_code == 422
    print("[6] full-control update: profile, plan, fare, password, device, guards")

    print("\n[SUCCESS] Subscription lifecycle checks passed")


if __name__ == "__main__":
    run()
