"""
AIIS Backend V2 - Application Entry Point & Factory
===================================================
Production-style Flask application factory implementation for AIIS.
Provides:
  - Application factory: create_app()
  - Centralized extension initialization
  - Blueprint registration for all API domains
  - Standardized JSON error handlers
  - Structured logging
"""

import os
import logging
from typing import Optional, Union, Type
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from backend_v2.config import BaseConfig, get_config
from backend_v2.extensions import init_extensions
from backend_v2.routes import (
    health_bp,
    emergency_bp,
    coordination_bp,
    locations_bp,
    hospitals_bp,
    departments_bp,
    hospital_admin_bp,
    capacity_bp,
    sri_bp,
    auth_bp,
    appointments_bp,
    planned_bp,
    web_bp,
)
from backend_v2.utils.exceptions import AppException
from backend_v2.utils.responses import error_response


def configure_logging(app: Flask, config_class: Type[BaseConfig]) -> None:
    """Setup structured logging according to application configuration."""
    log_level = getattr(logging, config_class.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=config_class.LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app.logger.setLevel(log_level)
    app.logger.info(
        f"Logging initialized at level {config_class.LOG_LEVEL} for {config_class.APP_NAME}"
    )


def register_error_handlers(app: Flask) -> None:
    """Register uniform JSON error handlers for all exceptions."""

    @app.errorhandler(AppException)
    def handle_custom_app_exception(exc: AppException):
        """Handle custom application domain exceptions."""
        app.logger.warning(f"AppException: [{exc.error_code}] {exc.message}")
        return error_response(
            message=exc.message,
            code=exc.error_code,
            details=exc.details,
            status_code=exc.status_code,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        """Handle standard HTTP exceptions with consistent JSON envelope."""
        app.logger.warning(f"HTTPException: {exc.code} - {exc.description}")
        return error_response(
            message=exc.description or "HTTP request error",
            code=exc.name.upper().replace(" ", "_"),
            status_code=exc.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unhandled_exception(exc: Exception):
        """Catch-all handler for unhandled server errors (never leaks secrets)."""
        app.logger.exception(f"Unhandled Exception: {str(exc)}")
        return error_response(
            message="Internal server error.",
            code="INTERNAL_SERVER_ERROR",
            status_code=500,
        )


def register_blueprints(app: Flask) -> None:
    """Register all API domain blueprints with their designated URL prefixes."""
    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(emergency_bp, url_prefix="/api/emergency")
    app.register_blueprint(coordination_bp, url_prefix="/api/coordination")
    app.register_blueprint(locations_bp, url_prefix="/api/locations")
    app.register_blueprint(locations_bp, url_prefix="/api/location", name="locations_singular_alias")
    app.register_blueprint(hospitals_bp, url_prefix="/api/hospitals")
    app.register_blueprint(departments_bp, url_prefix="/api/departments")
    app.register_blueprint(hospital_admin_bp, url_prefix="/api/hospital")
    app.register_blueprint(capacity_bp, url_prefix="/api/hospitals")
    app.register_blueprint(sri_bp, url_prefix="/api/sri")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(appointments_bp, url_prefix="/api/appointments")
    app.register_blueprint(planned_bp, url_prefix="/api/planned")
    app.register_blueprint(web_bp)

    # Legacy frontend compatibility URL rules
    from backend_v2.routes.hospital_admin import update_beds_legacy
    from backend_v2.routes.sri import get_hospital_analytics

    app.add_url_rule(
        "/api/update-beds",
        view_func=update_beds_legacy,
        methods=["POST"],
        endpoint="api_update_beds_legacy",
    )
    app.add_url_rule(
        "/api/hospital-analytics/<hospital_id>",
        view_func=get_hospital_analytics,
        methods=["GET"],
        endpoint="api_hospital_analytics_legacy",
    )

    app.logger.info("All blueprints and legacy routes registered successfully.")


def create_app(config_name: Optional[Union[str, Type[BaseConfig]]] = None) -> Flask:
    """
    Application factory for AIIS Backend V2.

    Args:
        config_name: Name of environment ('development', 'testing', 'production')
                     or a configuration class.

    Returns:
        Configured Flask application instance.
    """
    # 1. Resolve presentation layer paths (templates & static)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    template_folder = os.path.join(parent_dir, "frontend", "templates")
    static_folder = os.path.join(parent_dir, "frontend", "static")
    public_folder = os.path.join(parent_dir, "public")
    if not os.path.exists(public_folder):
        public_folder = os.path.join(current_dir, "public")
    if not os.path.exists(template_folder):
        template_folder = os.path.join(current_dir, "templates")
    if not os.path.exists(static_folder):
        static_folder = os.path.join(current_dir, "static")

    # Instantiate Flask app with presentation layer support (SPA at public)
    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=public_folder if os.path.exists(public_folder) else static_folder,
        static_url_path="",
    )

    # 2. Resolve and apply configuration
    if isinstance(config_name, type) and issubclass(config_name, BaseConfig):
        config_class = config_name
    elif isinstance(config_name, str):
        config_class = get_config(config_name)
    else:
        config_class = get_config()

    app.config.from_object(config_class)

    # 3. Configure structured logging
    configure_logging(app, config_class)

    # 4. Initialize extensions (CORS, Supabase manager)
    init_extensions(app)

    # 5. Register standardized error handlers
    register_error_handlers(app)

    # 6. Register domain Blueprints
    register_blueprints(app)

    # 7. Presentation URL Compatibility Processor
    from flask import url_for as flask_url_for

    @app.context_processor
    def inject_url_for_compat():
        def compat_url_for(endpoint, **values):
            if "." not in endpoint and endpoint not in app.view_functions:
                candidate = f"web.{endpoint}"
                if candidate in app.view_functions:
                    return flask_url_for(candidate, **values)
            return flask_url_for(endpoint, **values)
        return dict(url_for=compat_url_for)

    def handle_url_build_error(error, endpoint, values):
        if "." not in endpoint:
            candidate = f"web.{endpoint}"
            if candidate in app.view_functions:
                return flask_url_for(candidate, **values)
        raise error

    app.url_build_error_handlers.append(handle_url_build_error)

    # 8. Legacy static assets fallback (/static/...)
    from flask import send_from_directory

    @app.route("/static/<path:filename>")
    def serve_legacy_static(filename):
        legacy_dir = os.path.join(parent_dir, "frontend", "static")
        if os.path.exists(os.path.join(legacy_dir, filename)):
            return send_from_directory(legacy_dir, filename)
        if os.path.exists(os.path.join(public_folder, filename)):
            return send_from_directory(public_folder, filename)
        return "Asset not found", 404

    app.logger.info(f"{config_class.APP_NAME} initialization complete.")
    return app


if __name__ == "__main__":
    # Canonical development and hackathon demo server entrypoint
    flask_app = create_app()
    server_port = int(os.getenv("PORT", 5000))
    server_debug = flask_app.config.get("DEBUG", False)
    flask_app.run(host="0.0.0.0", port=server_port, debug=server_debug)
