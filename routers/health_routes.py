import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth_utils import get_current_admin
import models
import schemas

router = APIRouter(tags=["Engine Health"])

HEARTBEAT_STALE_MINUTES = 15
MAX_DUMPS_PER_DRIVER_PER_DAY = 50
MAX_SCREEN_TEXT_CHARS = 8_000
MAX_NODES_JSON_CHARS = 60_000


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    # SQLite hands back naive datetimes even for timezone=True columns
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _percentile(values: List[int], pct: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))]


@router.post("/api/v1/rides/screen-dump")
def create_screen_dump(req: schemas.ScreenDumpCreate, db: Session = Depends(get_db)):
    """Stores a redacted offer-screen tree from a failed accept, so detectors can be fixed from real screens."""
    driver = db.query(models.Driver).filter(models.Driver.phone == req.driver_phone).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = db.query(models.ScreenDump).filter(
        models.ScreenDump.driver_phone == req.driver_phone, models.ScreenDump.created_at >= since
    ).count()
    if recent >= MAX_DUMPS_PER_DRIVER_PER_DAY:
        return {"status": "dropped", "reason": "daily limit reached"}

    dump = models.ScreenDump(
        driver_phone=req.driver_phone,
        platform=req.platform[:50],
        kind=req.kind[:30],
        client_ride_id=req.client_ride_id,
        app_version=req.app_version,
        device_model=(req.device_model or "")[:100] or None,
        screen_width=req.screen_width,
        screen_height=req.screen_height,
        screen_text=(req.screen_text or "")[:MAX_SCREEN_TEXT_CHARS],
        nodes_json=(req.nodes_json or "")[:MAX_NODES_JSON_CHARS],
    )
    db.add(dump)
    db.commit()
    return {"status": "ok", "id": dump.id}


@router.get("/api/v1/admin/engine-health")
def engine_health(db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    """Per-driver engine liveness from heartbeats; stale = active driver with no heartbeat in 15 min."""
    now = datetime.now(timezone.utc)
    rows = []
    for d in db.query(models.Driver).order_by(models.Driver.id.desc()).all():
        last = _as_utc(d.last_heartbeat_at)
        minutes = round((now - last).total_seconds() / 60, 1) if last else None
        try:
            status = json.loads(d.engine_status) if d.engine_status else None
        except ValueError:
            status = None
        rows.append({
            "phone": d.phone,
            "name": d.name,
            "status": d.status,
            "app_version": d.app_version,
            "last_heartbeat_at": last.isoformat() if last else None,
            "minutes_since_heartbeat": minutes,
            "stale": d.status == "active" and (minutes is None or minutes > HEARTBEAT_STALE_MINUTES),
            "engine": status,
        })
    return rows


@router.get("/api/v1/admin/accept-quality")
def accept_quality(days: int = 1, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    """Per-platform verified accept outcomes and offer-to-click latency over the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 30)))
    rides = db.query(models.RideLog).filter(
        models.RideLog.status == "accepted", models.RideLog.created_at >= since
    ).all()

    by_platform = {}
    for r in rides:
        p = by_platform.setdefault(r.platform, {"platform": r.platform, "total": 0, "outcomes": {}, "latencies": []})
        p["total"] += 1
        outcome = r.verified_status or "Not verified"
        p["outcomes"][outcome] = p["outcomes"].get(outcome, 0) + 1
        if r.latency_ms is not None:
            p["latencies"].append(r.latency_ms)

    result = []
    for p in by_platform.values():
        verified = sum(c for k, c in p["outcomes"].items() if k != "Not verified")
        accepted = p["outcomes"].get("Accepted", 0)
        result.append({
            "platform": p["platform"],
            "total": p["total"],
            "outcomes": p["outcomes"],
            "success_rate": round(accepted / verified * 100, 1) if verified else None,
            "latency_p50_ms": _percentile(p["latencies"], 0.5),
            "latency_p90_ms": _percentile(p["latencies"], 0.9),
        })
    return sorted(result, key=lambda x: x["total"], reverse=True)


@router.get("/api/v1/admin/screen-dumps", response_model=List[schemas.ScreenDumpSummary])
def list_screen_dumps(platform: Optional[str] = None, limit: int = 50,
                      db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    q = db.query(models.ScreenDump)
    if platform:
        q = q.filter(models.ScreenDump.platform == platform)
    return q.order_by(models.ScreenDump.id.desc()).limit(max(1, min(limit, 200))).all()


@router.get("/api/v1/admin/screen-dumps/{dump_id}", response_model=schemas.ScreenDumpDetail)
def get_screen_dump(dump_id: int, db: Session = Depends(get_db), _: dict = Depends(get_current_admin)):
    dump = db.query(models.ScreenDump).filter(models.ScreenDump.id == dump_id).first()
    if not dump:
        raise HTTPException(status_code=404, detail="Screen dump not found")
    return dump


@router.get("/api/v1/keep-alive")
def get_keep_alive():
    """Return cloud instance keep-alive engine status and self-ping stats."""
    from keep_alive import get_keep_alive_status
    return get_keep_alive_status()


@router.post("/api/v1/keep-alive/ping")
def trigger_keep_alive():
    """Trigger an immediate keep-alive ping (can be called by admin or external webhooks)."""
    from keep_alive import trigger_manual_ping
    return trigger_manual_ping()

