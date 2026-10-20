# AutoRide Backend 24/7 Keep-Alive Architecture

## Overview & The Problem Solved
On **Render.com's Free Web Service tier**, instances automatically spin down (sleep) after **15 minutes of inactivity** (i.e., no inbound HTTP traffic through the public URL). 

When a sleeping instance receives a request:
- It requires a **Cold Start of 50 seconds or more** before responding.
- Mobile driver apps experience request timeouts, failed logins, and delayed ride accepts.
- Admin dashboard and public landing pages feel slow or unresponsive.

To permanently eliminate cold starts and keep the backend **100% LIVE and HOT 24/7**, AutoRide employs a **multi-tiered keep-alive strategy**.

---

## 3-Layer Zero-Downtime Architecture

```
                  ┌────────────────────────────────────────┐
                  │        Render.com Edge Router          │
                  │   (Resets 15-min idle timer on ping)   │
                  └───────────────────▲────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
 ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
 │       LAYER 1        │  │       LAYER 2        │  │       LAYER 3        │
 │ Internal Self-Pinger │  │    GitHub Actions    │  │ External Free Ping   │
 │   (Every 9 minutes)  │  │   (Every 10 minutes) │  │  (UptimeRobot / Cron) │
 └──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

### Layer 1: Internal Self-Pinger (`keep_alive.py`)
- Starts automatically with FastAPI on server boot.
- Runs on a lightweight daemon background thread.
- Dispatches a public HTTPS request to:
  `https://autoride-backend.onrender.com/api/v1/health`
  every **9 minutes** (540 seconds).
- Because it sends an outbound request to the public URL, the request enters through Render's public edge proxy, registering as legitimate inbound traffic and resetting Render's 15-minute countdown clock.
- If a ping encounters a temporary network issue, it switches to a 45-second fast-retry loop instead of waiting 9 minutes.

### Layer 2: Cloud GitHub Actions Cron (`.github/workflows/keep_alive.yml`)
- Runs directly from GitHub cloud servers on a schedule: `cron: '*/10 * * * *'`.
- Sends an external `curl` health check with a 60-second timeout.
- **Why this is critical**: If Render ever restarts, crashes, or is deployed while idle, the internal Python process might be stopped. GitHub Actions pings from the outside, immediately waking the sleeping container and initiating the internal pinger!

### Layer 3: Free External Uptime Monitor (UptimeRobot / Cron-Job.org)
For absolute 99.99% multi-region redundancy, we recommend linking a free monitor:

#### Option A: UptimeRobot (Free 5-minute pings - Recommended)
1. Sign up for free at [uptimerobot.com](https://uptimerobot.com).
2. Click **Add New Monitor**.
3. Configure:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `AutoRide Backend Keep-Alive`
   - **URL / IP**: `https://autoride-backend.onrender.com/api/v1/health`
   - **Monitoring Interval**: `5 minutes`
4. Click **Create Monitor**.
*Done! UptimeRobot will ping the service every 5 minutes from servers around the world.*

#### Option B: Cron-job.org (Free 5 or 10-minute crons)
1. Sign up at [cron-job.org](https://cron-job.org).
2. Create Cronjob:
   - **URL**: `https://autoride-backend.onrender.com/api/v1/health`
   - **Schedule**: Every 5 or 10 minutes.
3. Save.

---

## Live Monitoring & Testing

### 1. In the Admin Portal
1. Open the Admin Dashboard: `https://autoride-backend.onrender.com/admin`
2. Navigate to the **Engine Health** tab.
3. The top card displays:
   - **Status**: `HOT (NO SLEEP)`
   - **Target Endpoint**: `https://autoride-backend.onrender.com/api/v1/health`
   - **Cycle**: `Every 9 mins (Render Safe)`
   - **Last Ping**: Real-time timestamp
   - **Latency**: Ping duration in ms
   - **Pings / Success Rate**: Cumulative stats
4. Click **⚡ Ping Now** to trigger an instantaneous ping and verify immediate connectivity.

### 2. Via REST API
- Check status:
  ```bash
  curl -X GET https://autoride-backend.onrender.com/api/v1/keep-alive
  ```
  Returns:
  ```json
  {
    "enabled": true,
    "running": true,
    "target_url": "https://autoride-backend.onrender.com/api/v1/health",
    "interval_seconds": 540,
    "total_pings": 15,
    "successful_pings": 15,
    "failed_pings": 0,
    "last_ping_at": "2026-10-20T07:40:00Z",
    "last_status_code": 200,
    "last_latency_ms": 110,
    "message": "Ping successful (200 in 110ms)"
  }
  ```

- Trigger manual keep-alive ping:
  ```bash
  curl -X POST https://autoride-backend.onrender.com/api/v1/keep-alive/ping
  ```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `KEEP_ALIVE_URL` | Auto-detected / Render URL | Target URL for keep-alive health check. |
| `KEEP_ALIVE_INTERVAL_SECONDS` | `540` (9 minutes) | Seconds between self-pings (Render limit: 900s). |
| `DISABLE_KEEP_ALIVE` | `false` | Set to `true` to disable background worker (e.g. during offline test suites). |
