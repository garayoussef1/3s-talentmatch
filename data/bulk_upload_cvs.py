"""
bulk_upload_cvs.py
==================
Upload en masse tous les CVs du dossier data/CVtest/ via l'API.
Résultat visible immédiatement dans le frontend.

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python data/bulk_upload_cvs.py

Options :
  --dir  <chemin>   dossier CVs  (défaut: data/CVtest)
  --url  <url>      API base URL (défaut: http://localhost:8000/api)
  --skip-existing   ne pas re-uploader les CVs déjà en base (par nom)
"""

import os
import sys
import time
import argparse
import requests

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_DIR   = os.path.join(os.path.dirname(__file__), "CVtest")
BASE_URL      = "http://localhost:8000/api"
ADMIN_EMAIL   = "admin@talentmatch.com"
ADMIN_PASSWORD = "Admin1234!"
ALLOWED_EXT   = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}

# ── Auth ──────────────────────────────────────────────────────────────────────

def login(session: requests.Session, base: str) -> bool:
    r = session.post(f"{base}/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        print(f"[ERREUR] Login échoué ({r.status_code}): {r.text[:200]}")
        return False
    token = r.json().get("access_token")
    session.headers["Authorization"] = f"Bearer {token}"
    print(f"[OK] Connecté — {ADMIN_EMAIL}\n")
    return True

# ── Upload ────────────────────────────────────────────────────────────────────

def get_existing_names(session: requests.Session, base: str) -> set[str]:
    r = session.get(f"{base}/candidates?limit=500")
    if r.status_code != 200:
        return set()
    data = r.json()
    items = data.get("candidates", data) if isinstance(data, dict) else data
    return {c.get("nom", "").lower() for c in items}


def upload_cv(session: requests.Session, base: str, path: str) -> dict:
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()
    mime = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")

    with open(path, "rb") as f:
        r = session.post(
            f"{base}/upload-cv",
            files={"file": (filename, f, mime)},
            timeout=60,
        )
    return r

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir",  default=DEFAULT_DIR)
    parser.add_argument("--url",  default=BASE_URL)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    cv_dir = args.dir
    base   = args.url.rstrip("/")

    if not os.path.isdir(cv_dir):
        print(f"[ERREUR] Dossier introuvable : {cv_dir}")
        sys.exit(1)

    # Lister les fichiers valides
    files = sorted([
        os.path.join(cv_dir, f) for f in os.listdir(cv_dir)
        if os.path.splitext(f)[1].lower() in ALLOWED_EXT
    ])

    if not files:
        print(f"[ERREUR] Aucun fichier PDF/DOCX/PNG trouvé dans {cv_dir}")
        sys.exit(1)

    print("=" * 60)
    print("  3S TALENTMATCH — Bulk Upload CVs")
    print("=" * 60)
    print(f"  Dossier : {cv_dir}")
    print(f"  Fichiers trouvés : {len(files)}")
    print("=" * 60 + "\n")

    session = requests.Session()
    if not login(session, base):
        sys.exit(1)

    existing = get_existing_names(session, base) if args.skip_existing else set()

    ok = fail = skip = 0

    for i, path in enumerate(files, 1):
        name = os.path.basename(path)
        print(f"  [{i:02d}/{len(files)}] {name[:50]:<50}", end="  ", flush=True)

        if args.skip_existing and any(name[:6].lower() in e for e in existing):
            print("⏭  ignoré (déjà en base)")
            skip += 1
            continue

        t0 = time.time()
        try:
            r = upload_cv(session, base, path)
            elapsed = time.time() - t0

            if r.status_code in (200, 201):
                data = r.json()
                candidate_name = data.get("candidate_name") or data.get("nom") or "?"
                print(f"✓  {candidate_name:<25} ({elapsed:.1f}s)")
                ok += 1
            else:
                detail = r.json().get("detail", r.text[:60]) if r.headers.get("content-type","").startswith("application") else r.text[:60]
                print(f"✗  {r.status_code} — {detail}")
                fail += 1

        except Exception as e:
            print(f"✗  Erreur : {e}")
            fail += 1

    print()
    print("=" * 60)
    print(f"  Résultat : {ok} uploadés  |  {fail} échoués  |  {skip} ignorés")
    print(f"  → Frontend : http://localhost:3000/candidates")
    print("=" * 60)


if __name__ == "__main__":
    main()
