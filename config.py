"""
config.py — Serpify Central Configuration
==========================================
Single source of truth for ALL application settings.

Every module in this app should import settings from here:
    from config import settings

NEVER import os.environ directly in other files.
NEVER hardcode credentials anywhere else.
"""

import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# ─── Load .env file ───────────────────────────────────────────
# Looks for .env in the project root (same folder as this file).
# In production (Render, Railway, etc.), env vars are set via
# the platform dashboard — .env file won't exist and that's fine.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ─── Helper: require a value ──────────────────────────────────
def _require(key: str) -> str:
    """
    Reads an environment variable and raises a clear error if missing.
    This forces you to set all required vars before the app starts —
    much better than a cryptic crash 10 minutes in.
    """
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"\n\n❌ Missing required environment variable: {key}\n"
            f"   → Copy .env.example to .env and fill in all values.\n"
            f"   → See README.md for setup instructions.\n"
        )
    return value


def _get(key: str, default: str = "") -> str:
    """Reads an optional environment variable with a fallback default."""
    return os.getenv(key, default).strip()


# ══════════════════════════════════════════════════════════════
# APP SETTINGS
# ══════════════════════════════════════════════════════════════

class AppConfig:
    """Core application settings."""

    # Environment: "development" or "production"
    ENV: str = _get("APP_ENV", "development")

    # Product name shown in the UI
    NAME: str = _get("APP_NAME", "Serpify")

    # Secret key for signing session tokens.
    # Auto-generates a random key if not set (fine for local dev,
    # but sessions reset on restart — always set this in production).
    SECRET_KEY: str = _get("SECRET_KEY") or secrets.token_hex(32)

    @classmethod
    def is_production(cls) -> bool:
        return cls.ENV.lower() == "production"

    @classmethod
    def is_development(cls) -> bool:
        return cls.ENV.lower() == "development"


# ══════════════════════════════════════════════════════════════
# DATABASE SETTINGS
# ══════════════════════════════════════════════════════════════

class DatabaseConfig:
    """
    Database configuration.

    Logic:
    - If DATABASE_URL is set → use PostgreSQL (Supabase, Railway, etc.)
    - If DATABASE_URL is empty → use SQLite locally for development

    This means the same codebase works in both dev and production
    without any code changes — just set the env var.
    """

    # Raw URL from environment
    _raw_url: str = _get("DATABASE_URL", "")

    # Resolved URL: PostgreSQL if provided, else SQLite
    URL: str = _raw_url if _raw_url else f"sqlite:///{BASE_DIR / 'serpify.db'}"

    # Detect database type
    IS_POSTGRES: bool = _raw_url.startswith("postgresql://") or _raw_url.startswith("postgres://")
    IS_SQLITE: bool = not bool(_raw_url)

    @classmethod
    def get_display_name(cls) -> str:
        """Human-readable DB type — useful for logs and admin panel."""
        if cls.IS_POSTGRES:
            return "PostgreSQL (Production)"
        return "SQLite (Development)"


# ══════════════════════════════════════════════════════════════
# ADMIN BOOTSTRAP SETTINGS
# ══════════════════════════════════════════════════════════════

class AdminConfig:
    """
    First-run admin user credentials.

    These are read from env vars and used ONCE to create the
    initial admin account. After that, manage users in the app.

    WHY THIS IS SAFE:
    - The plain password is never stored in the database.
    - Only a bcrypt hash is stored.
    - These env vars can be deleted after first setup.
    """

    USERNAME: str = _get("ADMIN_USERNAME", "admin")
    PASSWORD: str = _get("ADMIN_PASSWORD", "")

    @classmethod
    def is_configured(cls) -> bool:
        """Returns True only if a real admin password has been set."""
        weak_defaults = {"", "REPLACE_WITH_YOUR_STRONG_PASSWORD_12_CHARS_MIN", "admin123", "password"}
        return cls.PASSWORD not in weak_defaults and len(cls.PASSWORD) >= 12

    @classmethod
    def validate(cls) -> None:
        """
        Called at app startup. Raises an error if admin password
        is missing or too weak. Forces good security from day one.
        """
        if not cls.PASSWORD:
            raise EnvironmentError(
                "\n\n❌ ADMIN_PASSWORD is not set in your .env file.\n"
                "   → Set a strong password (12+ characters).\n"
            )
        if len(cls.PASSWORD) < 12:
            raise EnvironmentError(
                f"\n\n❌ ADMIN_PASSWORD is too short ({len(cls.PASSWORD)} chars).\n"
                "   → Use at least 12 characters for security.\n"
            )


# ══════════════════════════════════════════════════════════════
# AI / GEMINI SETTINGS
# ══════════════════════════════════════════════════════════════

class AIConfig:
    """Google Gemini AI configuration."""

    GEMINI_API_KEY: str = _get("GEMINI_API_KEY", "")

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.GEMINI_API_KEY) and cls.GEMINI_API_KEY != "REPLACE_WITH_YOUR_GEMINI_KEY"


# ══════════════════════════════════════════════════════════════
# MAIN SETTINGS OBJECT
# ══════════════════════════════════════════════════════════════

class Settings:
    """
    Unified settings object. Import this everywhere:

        from config import settings
        print(settings.app.NAME)
        print(settings.db.URL)
        print(settings.admin.USERNAME)
    """
    app = AppConfig()
    db = DatabaseConfig()
    admin = AdminConfig()
    ai = AIConfig()

    def __repr__(self) -> str:
        return (
            f"Settings(\n"
            f"  app.ENV={self.app.ENV}\n"
            f"  app.NAME={self.app.NAME}\n"
            f"  db={self.db.get_display_name()}\n"
            f"  admin.USERNAME={self.admin.USERNAME}\n"
            f"  admin.configured={self.admin.is_configured()}\n"
            f"  ai.configured={self.ai.is_configured()}\n"
            f")"
        )


# ── Create the global settings instance ───────────────────────
# This is the object all other modules import.
settings = Settings()


# ── Dev-only: print config summary on import ──────────────────
if settings.app.is_development():
    print(f"\n✅ Serpify Config Loaded:")
    print(f"   ENV      → {settings.app.ENV}")
    print(f"   DATABASE → {settings.db.get_display_name()}")
    print(f"   ADMIN    → {settings.admin.USERNAME}")
    print(f"   GEMINI   → {'✓ configured' if settings.ai.is_configured() else '✗ not set'}\n")
