"""Reset DB data (users + CVs) and seed a fresh admin.

Usage (from repo root):
  .\.venv-10\Scripts\python.exe .\backend\scripts\reset_db_and_seed_admin.py

This script is destructive: it truncates key tables.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from any working directory
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text

from app.database import engine, SessionLocal
from app.models.user import UserRole
from app.services.auth_service import create_user, get_user_by_email


TABLES_TO_TRUNCATE = [
    "matches",
    "cv_documents",
    "candidates",
    "job_offers",
    "users",
]


def truncate_tables() -> None:
    # PostgreSQL: TRUNCATE ... CASCADE removes dependent rows.
    tables_sql = ", ".join(TABLES_TO_TRUNCATE)
    stmt = text(f"TRUNCATE TABLE {tables_sql} RESTART IDENTITY CASCADE;")
    with engine.begin() as conn:
        conn.execute(stmt)


def seed_admin(*, username: str, password: str, email: str) -> None:
    db = SessionLocal()
    try:
        existing = get_user_by_email(db, email)
        if existing:
            # Should not happen after truncate, but keep safe.
            return

        user = create_user(
            db,
            nom=username,
            prenom=username,
            email=email,
            password=password,
            role=UserRole.admin,
        )
        # No email flow for dev seed.
        user.is_email_verified = True
        user.is_active = True
        db.commit()
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset DB (users + CVs) and seed an admin")
    parser.add_argument("--admin-username", default="admin1")
    parser.add_argument(
        "--admin-email",
        default="admin1@local.test",
        help="Email is required by current auth/login schema; use a placeholder if needed.",
    )
    parser.add_argument("--admin-password", default=None, required=True)
    args = parser.parse_args()

    truncate_tables()
    seed_admin(username=args.admin_username, password=args.admin_password, email=args.admin_email)

    print("✅ Database reset done.")
    print(f"✅ Admin created: username={args.admin_username} email={args.admin_email} role=admin")
    print("(Password not printed.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
