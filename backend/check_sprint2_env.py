"""Vérification environnement Sprint 2"""
import sys

print("="*70)
print("VÉRIFICATION ENVIRONNEMENT SPRINT 2")
print("="*70)

# Vérifier spaCy
print("\n1. spaCy:")
try:
    import spacy
    print(f"   ✅ Installé - Version: {spacy.__version__}")
    
    # Vérifier modèle français
    try:
        nlp = spacy.load("fr_core_news_md")
        print(f"   ✅ Modèle français chargé: fr_core_news_md")
    except:
        print(f"   ⚠️  Modèle français NON installé")
        print(f"   → Installer avec: python -m spacy download fr_core_news_md")
except ImportError:
    print(f"   ❌ NON installé")
    print(f"   → Installer avec: pip install spacy")

# Vérifier autres dépendances Sprint 1
print("\n2. Dépendances Sprint 1:")
deps = [
    ("fastapi", "FastAPI"),
    ("sqlalchemy", "SQLAlchemy"),
    ("pypdf", "PyPDF"),
    ("docx", "python-docx"),
    ("easyocr", "EasyOCR"),
    ("pytest", "Pytest")
]

for module_name, display_name in deps:
    try:
        mod = __import__(module_name)
        version = getattr(mod, "__version__", "?")
        print(f"   ✅ {display_name}: {version}")
    except ImportError:
        print(f"   ❌ {display_name}: NON installé")

print("\n" + "="*70)
print("\n💡 Prochaines étapes Sprint 2:")
print("   1. Installer spaCy: pip install spacy")
print("   2. Télécharger modèle FR: python -m spacy download fr_core_news_md")
print("   3. Créer structure services/nlp/")
print("   4. Implémenter premier extracteur NLP")
