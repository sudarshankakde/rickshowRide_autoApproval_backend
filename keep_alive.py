"""
Cloud Instance Keep-Alive Engine for Render.com Free Tier.
Prevents free-tier web services from spinning down after 15 minutes of inactivity
by dispatching public HTTP health pings every 9 minutes.
"""
import os
import time
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("keep_alive")
logger.setLevel(logging.INFO)

# Default: 540 seconds (9 minutes) - safe buffer below Render's 15-minute idle limit
DEFAULT_INTERVAL_SECONDS = 540
DEFAULT_URL = "https://autoride-backend.onrender.com/api/v1/health"

_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_trigger_event = threading.Event()
_stats_lock = threading.Lock()

_stats: Dict[str, Any] = {
    "enabled": True,
    "running": False,
    "target_url": DEFAULT_URL,
    "interval_seconds": DEFAULT_INTERVAL_SECONDS,
    "total_pings": 0,
    "successful_pings": 0,
    "failed_pings": 0,
    "last_ping_at": None,
    "last_status_code": None,
    "last_latency_ms": None,
    "last_error": None,
    "started_at": None,
    "message": "Initialized"
}


def resolve_target_url() -> str:
    """Determine the public keep-alive target URL."""
    # 1. Explicit env override
    url = os.getenv("KEEP_ALIVE_URL")
    if url and url.strip():
        return url.strip()

    # 2. Render automatically injects RENDER_EXTERNAL_URL in production
    render_ext = os.getenv("RENDER_EXTERNAL_URL")
    if render_ext and render_ext.strip():
        base = render_ext.strip().rstrip("/")
        return f"{base}/api/v1/health"

    # 3. Known default production URL
    return DEFAULT_URL


def do_ping(url: str) -> Dict[str, Any]:
    """Execute an outbound HTTP GET ping to keep Render's edge proxy awake."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AutoRide-KeepAlive/1.0 (+https://autoride-backend.onrender.com; Render-Inactivity-Guard)",
            "Accept": "application/json, text/plain, */*",
        },
        method="GET"
    )

    t0 = time.time()
    status_code = None
    error_msg = None
    latency_ms = 0

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status_code = resp.status
            latency_ms = int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        status_code = e.code
        latency_ms = int((time.time() - t0) * 1000)
    except Exception as e:
        error_msg = str(e)
        latency_ms = int((time.time() - t0) * 1000)

    now_iso = datetime.now(timezone.utc).isoformat()
    # Any HTTP response from the edge router (including 200, 302, 401, 404) resets Render inactivity
    success = status_code is not None and status_code < 500

    with _stats_lock:
        _stats["total_pings"] += 1
        _stats["last_ping_at"] = now_iso
        _stats["last_status_code"] = status_code
        _stats["last_latency_ms"] = latency_ms
        if success:
            _stats["successful_pings"] += 1
            _stats["last_error"] = None
            _stats["message"] = f"Ping successful ({status_code} in {latency_ms}ms)"
        else:
            _stats["failed_pings"] += 1
            _stats["last_error"] = error_msg or f"HTTP {status_code}"
            _stats["message"] = f"Ping failed: {_stats['last_error']}"

    return {
        "success": success,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "error": error_msg,
        "timestamp": now_iso
    }


def _worker_loop():
    """Background daemon loop that periodically sends keep-alive pings."""
    logger.info("[KeepAlive] Worker loop started.")
    # Warm-up grace period before first ping (15 seconds)
    if _stop_event.wait(timeout=15):
        return

    while not _stop_event.is_set():
        target = resolve_target_url()
        with _stats_lock:
            _stats["target_url"] = target

        result = do_ping(target)
        if result["success"]:
            logger.info(f"[KeepAlive] Ping OK: {target} (code {result['status_code']} in {result['latency_ms']}ms)")
            wait_time = _stats["interval_seconds"]
        else:
            logger.warning(f"[KeepAlive] Ping failed: {target} ({result.get('error')}). Retrying in 45s...")
            wait_time = 45

        # Sleep in small slices so stop/trigger events interrupt immediately
        waited = 0
        while waited < wait_time and not _stop_event.is_set():
            if _trigger_event.is_set():
                _trigger_event.clear()
                break
            time.sleep(1)
            waited += 1

    logger.info("[KeepAlive] Worker loop stopped.")


def start_keep_alive():
    """Start the keep-alive background thread."""
    global _worker_thread

    # Check if explicitly disabled (e.g. for isolated test suites)
    if os.getenv("DISABLE_KEEP_ALIVE", "").lower() in ("true", "1", "yes"):
        with _stats_lock:
            _stats["enabled"] = False
            _stats["running"] = False
            _stats["message"] = "Disabled by DISABLE_KEEP_ALIVE"
        return

    # Interval configuration
    custom_interval = os.getenv("KEEP_ALIVE_INTERVAL_SECONDS")
    if custom_interval and custom_interval.isdigit():
        _stats["interval_seconds"] = max(60, int(custom_interval))

    _stop_event.clear()
    _trigger_event.clear()

    with _stats_lock:
        _stats["enabled"] = True
        _stats["running"] = True
        _stats["started_at"] = datetime.now(timezone.utc).isoformat()
        _stats["target_url"] = resolve_target_url()

    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(target=_worker_loop, name="AutoRideKeepAliveThread", daemon=True)
        _worker_thread.start()


def stop_keep_alive():
    """Signal the keep-alive thread to exit cleanly."""
    _stop_event.set()
    _trigger_event.set()
    with _stats_lock:
        _stats["running"] = False


def trigger_manual_ping() -> Dict[str, Any]:
    """Force an immediate ping and wake up next cycle."""
    target = resolve_target_url()
    result = do_ping(target)
    _trigger_event.set()
    return result


def get_keep_alive_status() -> Dict[str, Any]:
    """Return current keep-alive telemetry snapshot."""
    with _stats_lock:
        data = dict(_stats)
    data["target_url"] = resolve_target_url()
    return data
