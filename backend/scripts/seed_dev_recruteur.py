"""Seed (create or update) a dev recruiter user without relying on email OTP.

Usage (from repo root):
  .\.venv-10\Scripts\python.exe .\backend\scripts\seed_dev_recruteur.py --email recruteur@local.test --password "Recruiter123!"

This script is NON-DESTRUCTIVE: it does not truncate tables.
It simply creates (or updates) a user, sets role=recruteur and marks it as email-verified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_import_path() -> Path:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    return backend_dir


def _load_backend_env(backend_dir: Path) -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def main() -> int:
    backend_dir = _bootstrap_import_path()
    _load_backend_env(backend_dir)

    from app.database import SessionLocal
    from app.models.user import UserRole
    from app.services.auth_service import get_user_by_email, create_user, hash_password

    parser = argparse.ArgumentParser(description="Seed (create/update) a dev recruiter user")
    parser.add_argument("--email", default="recruteur@local.test")
    parser.add_argument("--password", required=True)
    parser.add_argument("--nom", default="Recruteur")
    parser.add_argument("--prenom", default="Dev")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = get_user_by_email(db, args.email)
        if user:
            user.nom = args.nom
            user.prenom = args.prenom
            user.role = UserRole.recruteur
            user.is_active = True
            user.is_email_verified = True
            user.hashed_password = hash_password(args.password)
            user.verification_code = None
            user.verification_code_expires = None
            db.commit()
            print(f"✅ Recruteur mis à jour: email={args.email} role=recruteur verified=True")
        else:
            user = create_user(
                db,
                nom=args.nom,
                prenom=args.prenom,
                email=args.email,
                password=args.password,
                role=UserRole.recruteur,
            )
            user.is_active = True
            user.is_email_verified = True
            user.verification_code = None
            user.verification_code_expires = None
            db.commit()
            print(f"✅ Recruteur créé: email={args.email} role=recruteur verified=True")

        print("(Mot de passe non affiché.)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
