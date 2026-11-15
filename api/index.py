"""Vercel entry point: exposes the AIIS Backend V2 Flask app as a Python function.

Static files in public/ are served by Vercel's CDN; /api/* and the staff pages
(login, dashboards) are rewritten here by vercel.json.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend_v2.app import create_app  # noqa: E402

app = create_app(os.getenv("FLASK_ENV") or "production")
