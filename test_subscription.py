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

    print("\n[SUCCESS] Subscription lifecycle checks passed")


if __name__ == "__main__":
    run()
