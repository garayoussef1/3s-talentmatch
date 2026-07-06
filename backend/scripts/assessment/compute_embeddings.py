"""
Pré-calcule les embeddings BGE-M3 des réponses de référence (Module 2).

Pour chaque OpenQuestion sans embeddings, encode ref_faible / ref_correct /
ref_expert et les stocke en JSON. Idempotent (ignore celles déjà calculées).

Usage (depuis backend/) : python -m scripts.assessment.compute_embeddings
"""
from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models.assessment import OpenQuestion
from app.services.assessment import semantic_scorer


def main():
    db = SessionLocal()
    done = 0
    try:
        questions = db.query(OpenQuestion).all()
        for q in questions:
            if q.emb_expert and q.emb_correct and q.emb_faible:
                continue
            vecs = semantic_scorer.embed([q.ref_faible, q.ref_correct, q.ref_expert])
            if vecs is None:
                print("BGE-M3 indisponible — abandon.")
                return
            q.emb_faible  = [float(x) for x in vecs[0]]
            q.emb_correct = [float(x) for x in vecs[1]]
            q.emb_expert  = [float(x) for x in vecs[2]]
            for col in ("emb_faible", "emb_correct", "emb_expert"):
                flag_modified(q, col)
            done += 1
        db.commit()
        print(f"Embeddings calculés pour {done} question(s) ouverte(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
