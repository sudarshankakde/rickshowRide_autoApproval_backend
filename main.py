import os
from datetime import date
from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

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

app = FastAPI(
    title="Auto Ride Sniper API",
    description="High-performance backend engine for multi-platform ride auto-accepting",
    version="1.0.3"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount Routers
app.include_router(admin_routes.router)
app.include_router(driver_routes.router)
app.include_router(ride_routes.router)
app.include_router(app_routes.router)
app.include_router(health_routes.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Auto Ride Sniper Backend",
        "version": "1.0.3",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
