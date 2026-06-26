# -*- coding: utf-8 -*-
"""Test rapide : génère les questions pour UN seul scénario (Ollama local)."""
import sys, io, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.interview.groq_interview_service import (
    CVSummary, OfferSummary, GroqInterviewService,
)

cv = CVSummary(
    nom="Youssef Garraya", email="youssef@example.com",
    competences=["Python", "FastAPI", "PostgreSQL", "Docker", "Git"],
    experiences=["Developpeur Backend chez StartupTech (2 ans)"],
    formations=["Ingenieur Informatique - INSAT Tunis (2024)"],
)
offer = OfferSummary(
    titre="Developpeur Backend Python Senior",
    domaine_metier="IT / Developpement",
    type_contrat="CDI",
    competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
    competences_appreciees=["Redis", "CI/CD"],
    description="Concevoir et maintenir des APIs REST haute performance.",
    niveau_seniorite="Senior",
)

svc = GroqInterviewService()
print(f"Provider: {svc.provider} | Model: {svc.model}")
print("Generation des questions (Mistral local, patience)...\n")
t0 = time.time()
questions = svc.generate_questions(cv, offer)
print(f"== {len(questions)} questions generees en {time.time()-t0:.0f}s ==\n")

for q in questions:
    print(f"[{q.get('index')}] ({q.get('phase')}) {q.get('question')}")
    ref = q.get("cv_reference")
    if ref:
        print(f"      -> reference CV: {ref}")
    print()
