"""
AIIS Backend V2 - Extensions Module
===================================
Centralized initialisation of Flask extensions and third-party clients.
"""

import logging
from typing import Optional, Any
from flask import Flask
from flask_cors import CORS

logger = logging.getLogger("aiis.extensions")

# Initialize Flask-CORS instance
cors = CORS()


class SupabaseManager:
    """
    Supabase client lifecycle manager.
    Lazily initialises public (anon) and admin (service role) clients
    using credentials provided in Flask app configuration.
    """

    def __init__(self, app: Optional[Flask] = None):
        self._client: Optional[Any] = None
        self._admin_client: Optional[Any] = None
        self.url: str = ""
        self.anon_key: str = ""
        self.service_role_key: str = ""

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Bind Supabase configuration from Flask app."""
        self.url = app.config.get("SUPABASE_URL", "")
        self.anon_key = app.config.get("SUPABASE_ANON_KEY", "")
        self.service_role_key = app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")

        if not self.url or not self.anon_key:
            logger.info(
                "Supabase credentials not configured in environment. "
                "Supabase features will operate in disconnected/mock mode."
            )
        else:
            logger.info("Supabase client configured.")

    @property
    def is_configured(self) -> bool:
        """Check if minimum Supabase credentials are present."""
        return bool(self.url and self.anon_key)

    def get_client(self) -> Optional[Any]:
        """Return lazily initialized Supabase client."""
        if self._client is not None:
            return self._client

        if not self.is_configured:
            return None

        try:
            from supabase import create_client
            self._client = create_client(self.url, self.anon_key)
            return self._client
        except ImportError:
            logger.warning("supabase-py library is not installed.")
            return None
        except Exception as exc:
            logger.error(f"Failed to initialize Supabase client: {exc}")
            return None

    def get_admin_client(self) -> Optional[Any]:
        """Return admin client using service role key (for trusted server tasks)."""
        if self._admin_client is not None:
            return self._admin_client

        if not self.url or not self.service_role_key:
            return None

        try:
            from supabase import create_client
            self._admin_client = create_client(self.url, self.service_role_key)
            return self._admin_client
        except Exception as exc:
            logger.error(f"Failed to initialize Supabase admin client: {exc}")
            return None


supabase = SupabaseManager()


def init_extensions(app: Flask) -> None:
    """Initialize all Flask extensions with the app instance."""
    import re
    # Setup CORS with allowed origins and headers from configuration
    allowed_origins = list(app.config.get("CORS_ORIGINS", ["*"]))
    # Dynamically allow any localhost or 127.0.0.1 port and null origin (file://)
    local_pattern = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")
    if local_pattern not in allowed_origins:
        allowed_origins.append(local_pattern)
    if "null" not in allowed_origins:
        allowed_origins.append("null")
    cors.init_app(
        app,
        resources={r"/api/*": {
            "origins": allowed_origins,
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-Tracking-Token",
                "x-tracking-token",
                "X-AIIS-Staff-Code",
                "x-aiis-staff-code",
                "Accept",
            ],
            "expose_headers": [
                "Content-Type",
                "Authorization",
                "X-Tracking-Token",
                "X-AIIS-Staff-Code",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        }},
        supports_credentials=True,
    )

    # Setup Supabase client
    supabase.init_app(app)

