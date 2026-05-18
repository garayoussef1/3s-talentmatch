import ast, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

# Syntaxe
ast.parse(open(
    os.path.join(os.path.dirname(__file__), '..', '..', 'backend',
                 'app', 'services', 'matching_sandbox', 'bert_scorer.py'),
    encoding='utf-8'
).read())
print("Syntaxe OK\n")

from app.services.matching_sandbox.bert_scorer import (
    _detect_seniority_level, _TECH_EXPANSION
)

# ── Test Action 3 : détection séniorité ──────────────────────────────────────
print("=== Action 3 — Séniorité ===")
tests_senior = [
    ("Développeur Python Senior",       4),
    ("Junior React Developer",           2),
    ("Stagiaire PFE DevOps",             1),
    ("Lead Data Scientist",              4),
    ("CTO / Directeur Technique",        5),
    ("Développeur Full Stack",           0),
    ("Expert Comptable Senior",          4),
    ("Alternant RH",                     1),
    ("Ingénieur confirmé middleware",    3),
]
for text, expected in tests_senior:
    got = _detect_seniority_level(text)
    ok = "OK" if got == expected else "ERREUR"
    print(f"  [{ok}] '{text}' -> niveau {got}  (attendu {expected})")

# ── Test Action 1 : nouveaux synonymes IT ────────────────────────────────────
print("\n=== Action 1 — Synonymes IT ===")
checks = [
    ("reactjs",     "react"),
    ("react",       "reactjs"),
    ("nodejs",      "node.js"),
    ("node.js",     "nodejs"),
    ("ts",          "typescript"),
    ("typescript",  "ts"),
    ("jest",        "tests unitaires"),
    ("pytest",      "tests unitaires"),
    ("golang",      "go"),
    ("go",          "golang"),
    ("spring boot", "java"),
    ("java",        "spring boot"),
    ("django",      "python"),
    ("fastapi",     "python"),
    ("graphql",     "apollo"),
    ("git",         "github"),
    ("mongodb",     "nosql"),
    ("elasticsearch", "elk"),
    ("vue",         "nuxt"),
    ("angular",     "typescript"),
    ("c#",          ".net"),
    ("tailwind",    "css"),
    ("cypress",     "e2e testing"),
    ("langchain",   "llm"),
]
ok_count = 0
for key, expected_in in checks:
    found = expected_in in _TECH_EXPANSION.get(key, frozenset())
    ok = "OK" if found else "ERREUR"
    if found:
        ok_count += 1
    print(f"  [{ok}] {key:<20} -> contient '{expected_in}'")

print(f"\nResultat: {ok_count}/{len(checks)} synonymes OK")
