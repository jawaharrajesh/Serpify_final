"""
auth/utils.py — Serpify Authentication Utilities
=================================================
Handles all user authentication: creation, verification, session management.

Security principles applied:
  1. Passwords are NEVER stored in plain text — only bcrypt hashes.
  2. Admin credentials come from environment variables, not code.
  3. Constant-time comparison prevents timing attacks.
  4. All failures log warnings but return generic errors to the user.

Usage:
    from auth.utils import create_user, verify_user, bootstrap_admin
"""

import logging
import re
from datetime import datetime
from typing import Optional

import bcrypt

from analytics.db import get_db_cursor
from config import settings

# ─── Logging ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────

# bcrypt work factor — higher = slower to brute-force.
# 12 is the recommended minimum for 2024+.
# Each increment doubles the time: 12 ≈ 250ms, 13 ≈ 500ms, 14 ≈ 1s.
BCRYPT_ROUNDS = 12

# Username rules
USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 50
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

# Password rules
PASSWORD_MIN_LEN = 8


# ══════════════════════════════════════════════════════════════
# PASSWORD HASHING
# ══════════════════════════════════════════════════════════════

def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.

    Why bcrypt:
    - Automatically includes a random salt (no collision attacks).
    - Deliberately slow — makes brute-force attacks impractical.
    - Industry standard since 1999, still recommended today.

    Returns:
        A bcrypt hash string (starts with "$2b$").
        Safe to store directly in the database.
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def check_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hash.

    Uses constant-time comparison internally (bcrypt does this).
    This prevents timing attacks — an attacker can't tell how many
    characters matched based on how long the comparison took.

    Returns:
        True if password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        # If hash is malformed or any error occurs, always return False.
        # Never let an exception reveal anything about the password.
        return False


# ══════════════════════════════════════════════════════════════
# USER VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_username(username: str) -> tuple[bool, str]:
    """
    Validates a username against the rules.

    Returns:
        (is_valid: bool, error_message: str)
        error_message is empty string if valid.
    """
    if not username:
        return False, "Username cannot be empty."
    if len(username) < USERNAME_MIN_LEN:
        return False, f"Username must be at least {USERNAME_MIN_LEN} characters."
    if len(username) > USERNAME_MAX_LEN:
        return False, f"Username cannot exceed {USERNAME_MAX_LEN} characters."
    if not USERNAME_PATTERN.match(username):
        return False, "Username can only contain letters, numbers, dots, dashes, and underscores."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validates a password meets minimum strength requirements.

    Returns:
        (is_valid: bool, error_message: str)
    """
    if not password:
        return False, "Password cannot be empty."
    if len(password) < PASSWORD_MIN_LEN:
        return False, f"Password must be at least {PASSWORD_MIN_LEN} characters."
    return True, ""


# ══════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════

def user_exists(username: str) -> bool:
    """
    Checks if a username already exists in the database.

    Returns:
        True if user exists, False otherwise.
    """
    with get_db_cursor(commit=False) as cur:
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cur.fetchone() is not None


def create_user(
    username: str,
    plain_password: str,
    email: str = "",
    plan: str = "free",
    is_admin: bool = False,
) -> tuple[bool, str]:
    """
    Creates a new user account.

    The plain password is hashed immediately and the original is
    never stored. This function is safe to call multiple times
    for the same username — it will not create duplicates.

    Args:
        username:       Unique username.
        plain_password: Plain-text password (will be hashed).
        email:          Optional email address.
        plan:           Subscription plan ("free", "starter", "pro", "agency").
        is_admin:       Whether this user has admin privileges.

    Returns:
        (success: bool, message: str)
    """
    # Validate inputs
    valid_user, user_error = validate_username(username)
    if not valid_user:
        return False, user_error

    valid_pass, pass_error = validate_password(plain_password)
    if not valid_pass:
        return False, pass_error

    # Check for duplicate
    if user_exists(username):
        logger.info(f"create_user: '{username}' already exists, skipping.")
        return True, f"User '{username}' already exists."

    # Hash the password BEFORE touching the database
    hashed = hash_password(plain_password)

    try:
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO users (username, password, email, plan, is_admin)
                VALUES (?, ?, ?, ?, ?)
            """, (username, hashed, email, plan, 1 if is_admin else 0))

        logger.info(f"create_user: created user '{username}' (plan={plan}, admin={is_admin})")
        return True, f"User '{username}' created successfully."

    except Exception as e:
        logger.error(f"create_user: failed for '{username}': {e}")
        return False, "Failed to create user. Please try again."


def verify_user(username: str, plain_password: str) -> bool:
    """
    Verifies a username + password combination.

    Security notes:
    - Always performs the password check even if the user doesn't
      exist (prevents user enumeration via timing).
    - Uses bcrypt's constant-time comparison.
    - Logs failed attempts for monitoring (but never logs passwords).
    - Updates last_login timestamp on success.

    Returns:
        True if credentials are correct AND account is active.
        False for any failure (user not found, wrong password, inactive).
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(
                "SELECT password, is_active FROM users WHERE username = ?",
                (username,)
            )
            row = cur.fetchone()

        if row is None:
            # User doesn't exist — still run a dummy hash check to
            # prevent timing attacks (don't return early).
            _dummy_hash_check(plain_password)
            logger.warning(f"verify_user: unknown user '{username}'")
            return False

        stored_hash = row["password"] if hasattr(row, "keys") else row[0]
        is_active = row["is_active"] if hasattr(row, "keys") else row[1]

        # Check account status
        if not is_active:
            logger.warning(f"verify_user: inactive account '{username}'")
            return False

        # Verify password
        if not check_password(plain_password, stored_hash):
            logger.warning(f"verify_user: wrong password for '{username}'")
            return False

        # Success — update last login timestamp
        _update_last_login(username)
        logger.info(f"verify_user: successful login for '{username}'")
        return True

    except Exception as e:
        logger.error(f"verify_user: unexpected error for '{username}': {e}")
        return False


def _dummy_hash_check(password: str) -> None:
    """
    Performs a fake bcrypt check to consume time.

    WHY: If we return immediately when a user doesn't exist,
    an attacker can tell which usernames are valid by measuring
    how fast the login fails. This takes the same time either way.
    """
    dummy_hash = "$2b$12$dummyhashfortimingprotectionXXXXXXXXXXXXXXXXXXXXXXX"
    try:
        bcrypt.checkpw(password.encode("utf-8"), dummy_hash.encode("utf-8"))
    except Exception:
        pass


def _update_last_login(username: str) -> None:
    """Updates the last_login timestamp for a user."""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login = ? WHERE username = ?",
                (datetime.utcnow().isoformat(), username)
            )
    except Exception as e:
        logger.warning(f"_update_last_login: could not update for '{username}': {e}")


# ══════════════════════════════════════════════════════════════
# ADMIN BOOTSTRAP
# ══════════════════════════════════════════════════════════════

def bootstrap_admin() -> None:
    """
    Creates the initial admin user on first startup.

    Reads credentials from environment variables (ADMIN_USERNAME,
    ADMIN_PASSWORD) — never from hardcoded values in source code.

    This function is idempotent: safe to call on every startup.
    If the admin user already exists, it does nothing.

    Raises:
        EnvironmentError: If ADMIN_PASSWORD is not set or too weak.
    """
    # This will raise an error if password is not set or too short.
    # Better to crash on startup with a clear message than to run
    # with no admin account or a weak password.
    settings.admin.validate()

    admin_username = settings.admin.USERNAME
    admin_password = settings.admin.PASSWORD

    if user_exists(admin_username):
        logger.info(f"bootstrap_admin: admin '{admin_username}' already exists.")
        return

    success, message = create_user(
        username=admin_username,
        plain_password=admin_password,
        email="",
        plan="agency",
        is_admin=True,
    )

    if success:
        logger.info(f"bootstrap_admin: ✅ Admin user '{admin_username}' created.")
    else:
        logger.error(f"bootstrap_admin: ❌ Failed: {message}")
        raise RuntimeError(f"Could not create admin user: {message}")


def get_user_plan(username: str) -> Optional[str]:
    """
    Returns the subscription plan for a user.

    Returns:
        Plan name ("free", "starter", "pro", "agency") or None if not found.
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute("SELECT plan FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if row:
                return row["plan"] if hasattr(row, "keys") else row[0]
    except Exception as e:
        logger.error(f"get_user_plan: error for '{username}': {e}")
    return None


def is_admin(username: str) -> bool:
    """Returns True if the user has admin privileges."""
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if row:
                val = row["is_admin"] if hasattr(row, "keys") else row[0]
                return bool(val)
    except Exception as e:
        logger.error(f"is_admin: error for '{username}': {e}")
    return False
