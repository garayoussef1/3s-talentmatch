"""
Corrige a posteriori les noms de candidats déjà en base quand ils sont faux
(intitulés de service, noms d'établissements...) en les redérivant depuis l'email.

Stratégie GÉNÉRALE (pas de blacklist) :
- On ne remplace QUE si le nom dérivé de l'email est "propre" : pas suspect et
  aucun de ses mots n'est un mot courant/métier (zipf < 4.2). Cela évite de
  remplacer un nom valide par un email pollué (ex: "Expert-Comptablejean.dupont@").
- On remplace si le nom actuel est suspect OU ne partage aucun token avec l'email.

Usage (depuis backend/) :
    python -m scripts.fix_candidate_names            # applique
    python -m scripts.fix_candidate_names --dry-run  # aperçu seulement
"""
import re
import sys

from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models.candidate import Candidate
from app.services.nlp.nlp_parser import NLPParser

try:
    from wordfreq import zipf_frequency as _zipf
except Exception:
    _zipf = None


def _email_name_clean(parser: NLPParser, name: str) -> bool:
    """True si le nom dérivé de l'email est fiable (pas de mot courant/métier)."""
    if not name or parser._is_name_suspicious(name):
        return False
    toks = [t for t in re.findall(r"[a-zà-öø-ÿ]+", name.lower()) if len(t) >= 3]
    if len(toks) < 2:
        return False
    if _zipf is None:
        return True
    return all(max(_zipf(t, "fr"), _zipf(t, "en")) < 4.2 for t in toks)


def main(dry_run: bool = False) -> None:
    db = SessionLocal()
    parser = NLPParser()
    fixed = 0
    try:
        for c in db.query(Candidate).all():
            email_name = parser._derive_name_from_email(c.email)
            current = c.nom or ""
            current_bad = parser._is_name_suspicious(current) or (
                email_name and not parser._names_overlap(current, email_name)
            )
            if email_name and _email_name_clean(parser, email_name) and current_bad:
                print(f"  {current!r} -> {email_name!r}  ({c.email})")
                if not dry_run:
                    c.nom = email_name
                    pd = c.parsed_data or {}
                    if isinstance(pd.get("identite"), dict):
                        pd["identite"]["nom_complet"] = email_name
                        c.parsed_data = pd
                        flag_modified(c, "parsed_data")
                fixed += 1
        if not dry_run:
            db.commit()
        print(f"\n{fixed} candidat(s) {'à corriger' if dry_run else 'corrigés'}.")
    finally:
        db.close()


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
