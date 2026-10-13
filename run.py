import os
import sys
import uvicorn
from dotenv import load_dotenv

def main():
    load_dotenv()
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    print("=" * 65)
    print(" 🚀  AutoRide Sniper Backend Engine  ⚡")
    print("=" * 65)
    print(f" • Local API:       http://localhost:{port}")
    print(f" • Admin Portal:    http://localhost:{port}/admin")
    print(f" • Swagger Docs:    http://localhost:{port}/docs")
    print(f" • Health Check:    http://localhost:{port}/health")
    print(f" • Running Mode:    Hot-Reload Enabled")
    print("=" * 65)
    print(" Press Ctrl+C to stop server.\n")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
