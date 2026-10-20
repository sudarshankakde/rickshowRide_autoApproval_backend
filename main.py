import os
from datetime import date
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from render_templates import get_app_version, render_all_templates

load_dotenv()

from database import engine, Base, get_db
import models
from auth_utils import hash_password
from routers import admin_routes, driver_routes, ride_routes, app_routes, health_routes

# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

def auto_migrate():
    """Ensure database schema integrity and seed initial superadmin."""
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()

            # Migrate Drivers table
            if 'drivers' in existing_tables:
                columns = [col['name'] for col in inspector.get_columns('drivers')]
                cols_to_add = {
                    'password': 'VARCHAR(100)',
                    'vehicle_number': 'VARCHAR(50)',
                    'city': 'VARCHAR(50)',
                    'language': "VARCHAR(10) DEFAULT 'mr'",
                    'max_distance': 'FLOAT DEFAULT 5.0',
                    'is_tester': 'BOOLEAN DEFAULT 0',
                    'plan_tier': "VARCHAR(30) DEFAULT 'premium'",
                    'app_limit': 'INTEGER DEFAULT 14',
                    'custom_allowed_platforms': 'VARCHAR(500)',
                    'app_version': 'VARCHAR(50)',
                    'last_heartbeat_at': 'TIMESTAMP',
                    'engine_status': 'VARCHAR(500)'
                }
                for col_name, col_type in cols_to_add.items():
                    if col_name not in columns:
                        conn.execute(text(f"ALTER TABLE drivers ADD COLUMN {col_name} {col_type}"))

            # Migrate RideLogs table
            if 'ride_logs' in existing_tables:
                r_cols = [col['name'] for col in inspector.get_columns('ride_logs')]
                r_cols_to_add = {
                    'screenshot_url': 'VARCHAR(500)',
                    'system_min_fare': 'INTEGER',
                    'system_max_fare': 'INTEGER',
                    'system_max_distance': 'FLOAT',
                    'app_version': 'VARCHAR(50)',
                    'client_ride_id': 'VARCHAR(64)',
                    'latency_ms': 'INTEGER',
                    'verified_status': 'VARCHAR(30)',
                    'verified_reason': 'VARCHAR(255)'
                }
                for col_name, col_type in r_cols_to_add.items():
                    if col_name not in r_cols:
                        conn.execute(text(f"ALTER TABLE ride_logs ADD COLUMN {col_name} {col_type}"))

            conn.commit()

        # Seed initial admin if admins table has 0 records
        with Session(bind=engine) as db:
            admin_count = db.query(models.Admin).count()
            if admin_count == 0:
                sup_user = os.getenv("SUPERADMIN_USERNAME", "sudarshan")
                sup_pass = os.getenv("SUPERADMIN_PASSWORD", "Qweasdzx@1#")
                db.add(models.Admin(
                    username=sup_user,
                    hashed_password=hash_password(sup_pass),
                    name=sup_user.title(),
                    role="superadmin",
                    is_active=True
                ))
                db.commit()
    except Exception as e:
        print("[AutoMigrate] Notice:", e)

auto_migrate()

from contextlib import asynccontextmanager
from keep_alive import start_keep_alive, stop_keep_alive

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to keep Render backend instance 24/7 hot and awake."""
    start_keep_alive()
    yield
    stop_keep_alive()

app = FastAPI(
    title="Auto Ride Sniper API",
    description="High-performance backend engine for multi-platform ride auto-accepting",
    version="1.0.3",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files, templates & dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Initial template compilation for static directory sync
try:
    render_all_templates()
except Exception as e:
    print(f"[Main] Template compilation warning: {e}")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    showcase_dir = os.path.join(static_dir, "showcase")
    if os.path.exists(showcase_dir):
        css_dir = os.path.join(showcase_dir, "css")
        js_dir = os.path.join(showcase_dir, "js")
        if os.path.exists(css_dir):
            app.mount("/css", StaticFiles(directory=css_dir), name="showcase-css")
        if os.path.exists(js_dir):
            app.mount("/js", StaticFiles(directory=js_dir), name="showcase-js")

# Mount Routers
app.include_router(admin_routes.router)
app.include_router(driver_routes.router)
app.include_router(ride_routes.router)
app.include_router(app_routes.router)
app.include_router(health_routes.router)

@app.get("/api")
@app.get("/api/status")
@app.get("/api/v1/status")
def read_root():
    return {
        "status": "online",
        "service": "Auto Ride Sniper Backend",
        "version": get_app_version(),
        "engine": "zero-latency micro-tap dispatcher"
    }

@app.get("/health")
@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": date.today().isoformat(),
        "database": db_status,
        "service": "Auto Ride Sniper Backend",
        "version": "1.0.3"
    }

@app.get("/admin", response_class=HTMLResponse)
def get_admin_dashboard():
    admin_file = os.path.join(static_dir, "admin.html")
    if os.path.exists(admin_file):
        with open(admin_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AutoRide Admin Portal HTML Not Found</h1>"

@app.get("/", response_class=HTMLResponse)
@app.get("/showcase", response_class=HTMLResponse)
@app.get("/download", response_class=HTMLResponse)
def get_landing_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"app_version": get_app_version()})

@app.get("/download-apk")
@app.get("/download-latest-apk")
def download_apk_root():
    from routers.app_routes import download_latest_apk
    return download_latest_apk()

@app.get("/privacy", response_class=HTMLResponse)
def get_privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={"app_version": get_app_version()})

@app.get("/terms", response_class=HTMLResponse)
def get_terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html", context={"app_version": get_app_version()})

@app.get("/refund", response_class=HTMLResponse)
@app.get("/cancellation", response_class=HTMLResponse)
def get_refund_page(request: Request):
    return templates.TemplateResponse(request=request, name="refund.html", context={"app_version": get_app_version()})

@app.get("/contact", response_class=HTMLResponse)
@app.get("/support", response_class=HTMLResponse)
def get_contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html", context={"app_version": get_app_version()})

@app.get("/pricing", response_class=HTMLResponse)
def get_pricing_page(request: Request):
    return templates.TemplateResponse(request=request, name="pricing.html", context={"app_version": get_app_version()})

@app.get("/logo.png")
def get_root_logo():
    logo_path = os.path.join(static_dir, "logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
