"""
analytics/db.py — Serpify Database Layer
=========================================
Handles all database connections and schema initialization.

Supports:
  - SQLite  → local development (zero setup, auto-created)
  - PostgreSQL → production via Supabase, Railway, Render, etc.

The database type is chosen automatically based on DATABASE_URL
in your .env file. No code changes needed between environments.

Usage:
    from analytics.db import get_conn, init_db

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    conn.close()
"""

import sqlite3
import logging
from contextlib import contextmanager
from typing import Union

from config import settings

# ─── Logging ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# CONNECTION FACTORY
# ══════════════════════════════════════════════════════════════

def get_conn():
    """
    Returns a database connection for the current environment.

    - In development (no DATABASE_URL): returns a SQLite connection.
    - In production (DATABASE_URL set): returns a psycopg2 PostgreSQL connection.

    Both connection types support the same cursor interface used
    throughout the app. Your queries work unchanged in both modes.

    IMPORTANT: Always close connections after use.
    Prefer using get_db_cursor() context manager instead.

    Returns:
        sqlite3.Connection | psycopg2.connection
    """
    if settings.db.IS_POSTGRES:
        return _get_postgres_conn()
    else:
        return _get_sqlite_conn()


@contextmanager
def get_db_cursor(commit: bool = True):
    """
    Context manager that provides a cursor and auto-closes the connection.

    WHY USE THIS instead of get_conn() directly:
    - Automatically closes connection even if an exception occurs.
    - Optionally commits transaction on success.
    - Rolls back on error — keeps your data safe.

    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("INSERT INTO jobs (url) VALUES (?)", (url,))
        # Connection auto-closed, transaction auto-committed.

    Args:
        commit: If True, commits the transaction before closing.
                Set to False for read-only queries.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error (rolled back): {e}")
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# SQLITE CONNECTION (Development)
# ══════════════════════════════════════════════════════════════

def _get_sqlite_conn() -> sqlite3.Connection:
    """
    Creates a SQLite connection for local development.

    SQLite stores everything in a single file (serpify.db).
    Perfect for dev — no setup, no server, just works.
    NOT suitable for production with multiple concurrent users.
    """
    # Extract the file path from the sqlite:// URL
    # URL format: sqlite:////absolute/path/to/db.sqlite3
    db_path = settings.db.URL.replace("sqlite:///", "")

    conn = sqlite3.connect(db_path)

    # Enable WAL mode: allows multiple simultaneous readers.
    # Without this, SQLite locks completely on every write.
    conn.execute("PRAGMA journal_mode=WAL;")

    # Enforce foreign key constraints (SQLite ignores them by default!)
    conn.execute("PRAGMA foreign_keys=ON;")

    # Row factory: allows accessing columns by name (row["username"])
    # instead of index (row[0]). Much cleaner code.
    conn.row_factory = sqlite3.Row

    return conn


# ══════════════════════════════════════════════════════════════
# POSTGRESQL CONNECTION (Production)
# ══════════════════════════════════════════════════════════════

def _get_postgres_conn():
    """
    Creates a PostgreSQL connection for production.

    Uses psycopg2 (standard PostgreSQL driver for Python).
    Works with Supabase, Railway, Render, AWS RDS, etc.

    The connection string comes from DATABASE_URL in your .env.
    Format: postgresql://USER:PASSWORD@HOST:PORT/DATABASE
    """
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(settings.db.URL)

        # Use DictCursor so columns are accessible by name, same as SQLite.Row
        # This keeps query code identical between SQLite and PostgreSQL.
        conn.cursor_factory = psycopg2.extras.RealDictCursor

        return conn

    except ImportError:
        raise ImportError(
            "\n\n❌ psycopg2 is not installed.\n"
            "   Run: pip install psycopg2-binary\n"
        )
    except Exception as e:
        raise ConnectionError(
            f"\n\n❌ Could not connect to PostgreSQL.\n"
            f"   Check your DATABASE_URL in .env\n"
            f"   Error: {e}\n"
        )


# ══════════════════════════════════════════════════════════════
# SCHEMA INITIALIZATION
# ══════════════════════════════════════════════════════════════

# SQL to detect if a column exists varies by DB. These helpers
# abstract the difference so init_db() works for both.

_SQLITE_COLUMN_EXISTS = """
    SELECT COUNT(*) FROM pragma_table_info(?) WHERE name=?
"""

_POSTGRES_COLUMN_EXISTS = """
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_name = %s AND column_name = %s
"""


def _placeholder(is_postgres: bool) -> str:
    """
    SQLite uses ? as parameter placeholder.
    PostgreSQL uses %s.
    This tiny difference would break every query if not handled.
    """
    return "%s" if is_postgres else "?"


def init_db() -> None:
    """
    Initializes the database schema.

    - Creates all required tables if they don't exist.
    - Safely adds new columns to existing tables (non-destructive).
    - Safe to call on every startup — will not overwrite existing data.
    - Works identically on SQLite and PostgreSQL.

    Call this once at app startup before any other DB operations.
    """
    pg = settings.db.IS_POSTGRES
    ph = _placeholder(pg)  # "?" for SQLite, "%s" for PostgreSQL

    logger.info(f"Initializing database: {settings.db.get_display_name()}")

    with get_db_cursor() as cur:

        # ── Users table ───────────────────────────────────────
        # Stores all user accounts (admins + future SaaS users).
        # username is the primary key — unique, indexed automatically.
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                username    TEXT PRIMARY KEY,
                password    TEXT NOT NULL,
                email       TEXT,
                plan        TEXT DEFAULT 'free',
                is_admin    INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login  TIMESTAMP
            )
        """)

        # ── Audit jobs table ──────────────────────────────────
        # Records every SEO audit job run by any user.
        # user_id links back to users table.
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS audit_jobs (
                id          INTEGER {'GENERATED ALWAYS AS IDENTITY PRIMARY KEY' if pg else 'PRIMARY KEY AUTOINCREMENT'},
                user_id     TEXT NOT NULL,
                tool        TEXT NOT NULL,
                target_url  TEXT,
                status      TEXT DEFAULT 'pending',
                result_path TEXT,
                error_msg   TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)

        # ── Usage tracking table ───────────────────────────────
        # Tracks how many audits each user has run (for plan limits).
        # This is what powers Free vs Pro tier restrictions.
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS usage_tracking (
                id          INTEGER {'GENERATED ALWAYS AS IDENTITY PRIMARY KEY' if pg else 'PRIMARY KEY AUTOINCREMENT'},
                user_id     TEXT NOT NULL,
                action      TEXT NOT NULL,
                month_year  TEXT NOT NULL,
                count       INTEGER DEFAULT 1,
                UNIQUE(user_id, action, month_year),
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)

        # ── Settings table ────────────────────────────────────
        # Key-value store for app-wide settings (admin configurable).
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS app_settings (
                key         TEXT PRIMARY KEY,
                value       TEXT,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    
        # ── Jobs table ────────────────────────────────────────
        # Used by jobs/job_manager.py for background task tracking.
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                tool        TEXT NOT NULL,
                status      TEXT DEFAULT 'queued',
                params      TEXT DEFAULT '{{}}',
                result_json TEXT,
                result_excel TEXT,
                error       TEXT,
                created_at  REAL DEFAULT (strftime('%s','now')),
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)

    # ── Migrate existing tables ───────────────────────────────
    # Safely adds new columns without dropping existing data.
    _run_migrations()

    logger.info("✅ Database initialized successfully.")


def _run_migrations() -> None:
    """
    Adds new columns to existing tables without losing data.

    WHY THIS EXISTS: If users already have a running database,
    we can't just DROP and recreate tables. We add new columns
    only if they don't already exist.

    Add future schema changes here as new _add_column_if_missing() calls.
    """
    pg = settings.db.IS_POSTGRES

    # Example: if you add a new column to users in a future update,
    # add it here so existing databases get upgraded automatically.
    # _add_column_if_missing("users", "stripe_customer_id", "TEXT", pg)
    # _add_column_if_missing("users", "trial_ends_at", "TIMESTAMP", pg)


def _add_column_if_missing(table: str, column: str, col_type: str, is_postgres: bool) -> None:
    """
    Adds a column to a table only if it doesn't already exist.
    Used by _run_migrations() to safely upgrade the schema.
    """
    ph = _placeholder(is_postgres)

    with get_db_cursor() as cur:
        if is_postgres:
            cur.execute(_POSTGRES_COLUMN_EXISTS, (table, column))
        else:
            cur.execute(_SQLITE_COLUMN_EXISTS, (table, column))

        exists = cur.fetchone()[0]
        if not exists:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            logger.info(f"Migration: added column '{column}' to '{table}'")
