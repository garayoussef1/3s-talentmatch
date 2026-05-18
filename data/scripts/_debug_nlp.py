import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.nlp_parser import NLPParser

ext = CVExtractor(enable_ocr_fallback=False)
par = NLPParser()

path = os.path.join(os.path.dirname(__file__), '..', 'Cv', 'CV1_Aziz_Chahed_FullStack_3S.pdf')
r = ext.extract(path)
parsed = par.parse(r["text"])

print("=== CLÉS PARSED DATA ===")
print(list(parsed.keys()))
print()
for k, v in parsed.items():
    if isinstance(v, list) and v:
        print(f"  {k}: {v[:3]}")
    elif isinstance(v, dict) and v:
        print(f"  {k}: {dict(list(v.items())[:4])}")
    elif v:
        print(f"  {k}: {v}")

print()
print("=== TEXTE BRUT (300 chars) ===")
print(r["text"][:300])
