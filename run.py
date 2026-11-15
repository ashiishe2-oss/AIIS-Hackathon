"""
AIIS Backend V2 - Canonical Demo Server Entrypoint
==================================================
Runs the integrated Flask server on port 5000 serving:
1. REST API endpoints under /api/*
2. SPA frontend assets from public/ (index.html, styles.css, app.js, etc.)
"""

import os
from backend_v2.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"\n=======================================================")
    print(f" AIIS Integrated Platform running on http://{host}:{port}")
    print(f" SPA Web App: http://localhost:{port}/ or http://127.0.0.1:{port}/")
    print(f" RESTful API: http://localhost:{port}/api/health")
    print(f"=======================================================\n")
    # Run in stable demo mode with reloader disabled to prevent Windows/OneDrive watchdog interruptions
    app.run(host=host, port=port, debug=False, use_reloader=False)
