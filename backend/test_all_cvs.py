import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.nlp.nlp_parser import NLPParser

pe = PDFExtractor()
p = NLPParser()

cvs = {
    'Sarah EN':  r'..\data\Cv\sarah.pdf',
    'Ranim EN':  r'..\data\Cv\C_v_Pro_RanimEnglish.pdf',
    'Ranim FR':  r'..\data\Cv\C_v_Pro_RanimFrancais.pdf',
    'Thomas FR': r'..\data\Cv\thomas.pdf',
    'Othmen FR': r'..\data\Cv\othmen (1).pdf',
    'AhmedAziz': r'..\data\Cv\AhmedAziz_Ammar (1).pdf',
}

for label, path in cvs.items():
    if not os.path.exists(path):
        print(f"=== {label} === FICHIER INTROUVABLE: {path}")
        continue
    result = pe.extract(path)
    txt = result.get('text', '')
    r = p.parse(txt).get('parsed_data', {})
    nom = r.get('identite', {}).get('nom_complet', '?')
    forms = r.get('formations', [])
    exps = r.get('experiences', [])
    print(f"=== {label} ===")
    print(f"  NOM: {nom}")
    print(f"  FORMATIONS: {len(forms)}")
    for i, f in enumerate(forms):
        diplome = f.get('diplome', '')
        etab = f.get('etablissement', '')
        print(f"    F{i}: {diplome} @ {etab}")
    print(f"  EXPERIENCES: {len(exps)}")
    for i, e in enumerate(exps):
        poste = e.get('poste', '')
        co = e.get('entreprise', '')
        dd = e.get('date_debut', '')
        df = e.get('date_fin', '')
        print(f"    E{i}: poste={poste} | co={co} | {dd}-{df}")
    # Langues
    langues = r.get('langues', [])
    print(f"  LANGUES: {len(langues)}")
    for l in langues:
        if isinstance(l, dict):
            print(f"    - {l.get('langue','')} ({l.get('niveau','')})")
        else:
            print(f"    - {l}")
    # Compétences
    skills = r.get('competences', [])
    cats = r.get('competences_par_categorie', {})
    print(f"  COMPETENCES: {len(skills)}")
    for s in skills:
        print(f"    - {s}")
    if cats:
        print(f"  COMPETENCES PAR CATEGORIE:")
        for cat, items in cats.items():
            print(f"    [{cat}]: {', '.join(items)}")
    print()
