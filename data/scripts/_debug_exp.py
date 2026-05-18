"""
Debug : extraction années d'expérience sur les CVs 3S
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.nlp_parser import NLPParser

ext = CVExtractor(enable_ocr_fallback=False)
par = NLPParser()

CV_DIR = os.path.join(os.path.dirname(__file__), '..', 'Cv')

# CVs 3S à tester
test_cvs = [
    'CV1_Aziz_Chahed_FullStack_3S.pdf',
    'CV3_Nour_Trabelsi_Comptable.pdf',
    'CV1_Leila_Juriste_SIMPLE.pdf',
    'CV3_Khalil_Mansouri_DevOps.pdf',
    'CV2_Sarra_Khelifi_DataScientist.pdf',
]

for fname in test_cvs:
    path = os.path.join(CV_DIR, fname)
    if not os.path.exists(path):
        print(f"[ABSENT] {fname}")
        continue

    r = ext.extract(path)
    if not r.get('success'):
        print(f"[ECHEC EXTRACTION] {fname}")
        continue

    parsed = par.parse(r['text'])
    pd = parsed.get('parsed_data', parsed)

    meta     = pd.get('metadata') or {}
    exps     = pd.get('experiences') or []
    identite = pd.get('identite') or {}

    print(f"\n{'='*60}")
    print(f"CV : {fname}")
    print(f"  metadata.annees_experience_totales : {meta.get('annees_experience_totales')}")
    print(f"  metadata.niveau_formation_max      : {meta.get('niveau_formation_max')}")
    print(f"  identite.annees_experience         : {identite.get('annees_experience')}")
    print(f"  Nbre expériences trouvées          : {len(exps)}")
    for i, exp in enumerate(exps[:5]):
        print(f"    [{i}] poste={exp.get('poste') or exp.get('title','?')}  "
              f"debut={exp.get('date_debut') or exp.get('start_date','?')}  "
              f"fin={exp.get('date_fin') or exp.get('end_date','?')}  "
              f"duree={exp.get('duree_mois') or exp.get('duration_months','?')} mois")
    print(f"  TEXTE BRUT (400 chars):")
    print("  " + r['text'][:400].replace('\n', '\n  '))
