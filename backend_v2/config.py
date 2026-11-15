"""
AIIS Backend V2 - Configuration Module
======================================
Environment-driven configuration for development, testing, and production.
Reads credentials strictly from environment variables or .env.
"""

import os
from typing import List
from dotenv import load_dotenv

# Load .env file from the backend package directory if present, or cwd
_pkg_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_pkg_env):
    load_dotenv(_pkg_env)
else:
    load_dotenv()


class BaseConfig:
    """Base configuration shared across all environments."""

    # Application
    APP_NAME: str = "AIIS Backend V2"
    SERVICE_NAME: str = "AIIS Backend V2"
    APP_VERSION: str = "2.0.0"

    # Core Security
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "")
    JSON_SORT_KEYS: bool = False

    # CORS
    _raw_cors = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5000,http://localhost:3000,http://localhost:8080,http://localhost:5500,http://127.0.0.1:5173,http://127.0.0.1:5000,http://127.0.0.1:3000,http://127.0.0.1:8080,http://127.0.0.1:5500,null,https://aiis-livid.vercel.app"
    )
    CORS_ORIGINS: List[str] = [
        origin.strip() for origin in _raw_cors.split(",") if origin.strip()
    ]

    # Supabase Integration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "").strip()
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d] - %(message)s"

    # Testing & Debug flags
    DEBUG: bool = False
    TESTING: bool = False


class DevelopmentConfig(BaseConfig):
    """Configuration for local development."""

    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # Provide a development fallback if FLASK_SECRET_KEY is omitted
    if not BaseConfig.SECRET_KEY:
        SECRET_KEY = "dev-insecure-secret-key-change-in-production"


class TestingConfig(BaseConfig):
    """Configuration for automated testing."""

    TESTING: bool = True
    DEBUG: bool = True
    LOG_LEVEL: str = "WARNING"
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "test-secret-key-for-unit-tests-only")
    CORS_ORIGINS: List[str] = ["*"]


class ProductionConfig(BaseConfig):
    """Configuration for production deployment."""

    DEBUG: bool = False
    TESTING: bool = False
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __init__(self):
        super().__init__()
        # Enforce required secrets in production
        if not self.SECRET_KEY or self.SECRET_KEY == "replace_with_secure_random_secret":
            raise ValueError(
                "CRITICAL: FLASK_SECRET_KEY environment variable is missing or insecure in production mode."
            )


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None) -> type[BaseConfig]:
    """
    Resolve configuration class from name or FLASK_ENV environment variable.
    Defaults to DevelopmentConfig.
    """
    if env_name is None:
        env_name = os.getenv("FLASK_ENV", "development").lower()

    config_class = CONFIG_MAP.get(env_name, DevelopmentConfig)
    return config_class

