import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.nlp.nlp_parser import NLPParser

pe = PDFExtractor()
p = NLPParser()

path = r'..\data\Cv\AhmedAziz_Ammar (1).pdf'
result = pe.extract(path)
txt = result.get('text', '')

# 1. Texte brut (premières lignes)
print("=" * 60)
print("TEXTE BRUT (500 premiers chars):")
print("=" * 60)
print(txt[:500])

# 2. Texte normalisé
norm = p._normalize_pdf_text(txt)
print("\n" + "=" * 60)
print("TEXTE NORMALISE (premières 30 lignes):")
print("=" * 60)
for i, l in enumerate(norm.split('\n')[:30]):
    print(f"L{i}: [{l}]")

# 3. Parsing complet
r = p.parse(txt).get('parsed_data', {})
nom = r.get('identite', {}).get('nom_complet', '?')
forms = r.get('formations', [])
exps = r.get('experiences', [])
langues = r.get('langues', [])
skills = r.get('competences', [])
cats = r.get('competences_par_categorie', {})

print("\n" + "=" * 60)
print("RESULTATS EXTRACTION:")
print("=" * 60)
print(f"NOM: {nom}")
print(f"\nFORMATIONS: {len(forms)}")
for i, f in enumerate(forms):
    print(f"  F{i}: {f.get('diplome','')} @ {f.get('etablissement','')}")

print(f"\nEXPERIENCES: {len(exps)}")
for i, e in enumerate(exps):
    print(f"  E{i}: poste={e.get('poste','')} | co={e.get('entreprise','')} | {e.get('date_debut','')}-{e.get('date_fin','')}")

print(f"\nLANGUES: {len(langues)}")
for l in langues:
    if isinstance(l, dict):
        print(f"  - {l.get('langue','')} ({l.get('niveau','')})")
    else:
        print(f"  - {l}")

print(f"\nCOMPETENCES: {len(skills)}")
for s in skills:
    print(f"  - {s}")

if cats:
    print(f"\nCOMPETENCES PAR CATEGORIE:")
    for cat, items in cats.items():
        print(f"  [{cat}]: {', '.join(items)}")

# 4. Texte complet normalisé pour chercher les sections langues/compétences
print("\n" + "=" * 60)
print("RECHERCHE SECTIONS LANGUES/COMPETENCES:")
print("=" * 60)
for i, l in enumerate(norm.split('\n')):
    ll = l.lower()
    if any(k in ll for k in ['langue', 'language', 'compéten', 'skill', 'framework', 'technolog', 'outil', 'tool']):
        print(f"L{i}: [{l}]")
