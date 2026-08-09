import os
import sys
from dotenv import load_dotenv

# Load .env variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

db_url = os.getenv('DATABASE_URL')
print(f"Connecting to Database: {db_url}")

try:
    from database import engine, Base
    import models

    print("Initializing & migrating database tables on Neon PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("MIGRATION SUCCESSFUL! All database tables (drivers, ride_logs) are live on Neon PostgreSQL!")
except Exception as e:
    print(f"Migration Error: {e}")
    sys.exit(1)
