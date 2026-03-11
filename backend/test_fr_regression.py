"""Quick test script for FR CV regression."""
import sys, pathlib
sys.path.insert(0, ".")
from pypdf import PdfReader
from app.services.nlp.nlp_parser import NLPParser
from app.services.nlp.experience_extractor import ExperienceExtractor

p = NLPParser()

def test_cv(name, path, debug_blocks=False):
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    r = p.parse(text)
    pd = r["parsed_data"]
    ident = pd.get("identite", {})
    forms = pd.get("formations", [])
    exps = pd.get("experiences", [])
    nom = ident.get("nom_complet", ident.get("nom", "?"))
    print(f"=== {name} ===")
    print(f"NOM: {nom}")
    print(f"FORM: {len(forms)}")
    for i, f in enumerate(forms):
        print(f"  F{i}: diplome={f.get('diplome')}, etab={f.get('etablissement')}")
    print(f"EXP: {len(exps)}")
    for i, e in enumerate(exps):
        print(f"  E{i}: poste={e.get('poste')}, company={e.get('entreprise')}, {e.get('date_debut')}-{e.get('date_fin')}")
    if debug_blocks:
        norm = NLPParser._normalize_pdf_text(text)
        ee = ExperienceExtractor()
        section = ee._find_experience_section(norm)
        if section:
            blocks = ee._split_into_blocks(section)
            print(f"  BLOCKS ({len(blocks)}):")
            for bi, b in enumerate(blocks):
                preview = b[:120].replace(chr(10), " | ")
                print(f"    B{bi}: {preview}")
            print(f"  SECTION len={len(section)}")
        else:
            print("  NO EXPERIENCE SECTION FOUND")
        # Show all section headings in normalized text
        import re as _re
        headings = _re.findall(r'^(.{0,80})$', norm, _re.MULTILINE)
        caps_headings = [h for h in headings if h.strip().isupper() and len(h.strip()) > 3]
        if caps_headings:
            print(f"  HEADINGS: {caps_headings[:10]}")

# FR CVs
test_cv("RANIM FR", r"..\data\Cv\C_v_Pro_RanimFrancais.pdf", debug_blocks=True)
test_cv("THOMAS",   r"..\data\Cv\thomas.pdf", debug_blocks=True)
test_cv("OTHMEN",   r"..\data\Cv\othmen (1).pdf", debug_blocks=True)

# EN CVs (non-regression)
test_cv("SARAH",    r"..\data\Cv\sarah.pdf", debug_blocks=True)
test_cv("RANIM EN", r"..\data\Cv\C_v_Pro_RanimEnglish.pdf", debug_blocks=True)
