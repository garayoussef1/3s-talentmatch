"""
Test batch : teste TOUS les CVs de tous les dossiers
Formats : PDF, Word, Images
Sauvegarde chaque résultat en JSON
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.disable(logging.CRITICAL)

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.cv_parser import CVParser


# Dossiers à scanner
CV_DIRS = {
    "PDF"    : Path(r"..\data\cvs_raw\templates"),
    "Scannés": Path(r"..\data\cvs_raw\scanned"),
    "Word"   : Path(r"..\data\cvs_raw\word"),
}

# Extensions acceptées
EXTENSIONS = [".pdf", ".docx", ".png", ".jpg", ".jpeg"]

OUTPUT_DIR = Path(r"..\data\cvs_processed")


def test_all_cvs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    extractor = CVExtractor()
    parser    = CVParser()

    all_results = []
    total = 0
    success = 0
    failed  = 0

    print("\n╔" + "═"*68 + "╗")
    print("║" + " "*18 + "3S TALENTMATCH — TEST BATCH TOUS CVs" + " "*14 + "║")
    print("╚" + "═"*68 + "╝\n")

    for format_name, folder in CV_DIRS.items():
        if not folder.exists():
            print(f"  ⚠️  Dossier manquant : {folder}")
            continue

        files = [f for f in folder.iterdir() if f.suffix.lower() in EXTENSIONS]

        if not files:
            print(f"  ⚠️  Aucun fichier dans : {folder}")
            continue

        print(f"\n{'─'*70}")
        print(f"  📁 {format_name} ({len(files)} fichier(s)) — {folder}")
        print(f"{'─'*70}")

        for cv_file in files:
            total += 1
            t0 = time.time()

            print(f"\n  [{total}] {cv_file.name}")

            # Extraction
            ext_result = extractor.extract(str(cv_file))

            if not ext_result['success']:
                failed += 1
                print(f"       ❌ Extraction échouée : {ext_result['error']}")
                all_results.append({
                    "fichier": cv_file.name,
                    "format": ext_result['format'],
                    "extraction": "ÉCHEC",
                    "erreur": ext_result['error']
                })
                continue

            print(f"       ✅ Extraction OK — {len(ext_result['text'])} chars ({ext_result['method']})")

            # Parsing NLP
            cv_data = parser.parse(ext_result['text'])

            elapsed = round(time.time() - t0, 2)

            print(f"       👤 Nom        : {cv_data['identite']['nom_complet']}")
            print(f"       📧 Email      : {cv_data['contacts']['email'] or '—'}")
            print(f"       📞 Téléphone  : {cv_data['contacts']['telephone'] or '—'}")
            print(f"       💻 Compétences: {', '.join(cv_data['competences'][:6]) or '—'}")
            print(f"       🌍 Langues    : {', '.join(cv_data['langues']) or '—'}")
            print(f"       🏢 Expériences: {len(cv_data['experiences'])}")
            print(f"       🎓 Formations : {len(cv_data['formations'])}")
            print(f"       ⏱️  Temps      : {elapsed}s")

            # Sauvegarder le JSON individuel
            out_file = OUTPUT_DIR / f"{cv_file.stem}_result.json"
            full_result = {
                "fichier":    cv_file.name,
                "format":     ext_result['format'],
                "methode":    ext_result['method'],
                "nb_chars":   len(ext_result['text']),
                "temps_sec":  elapsed,
                "parsing":    cv_data
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(full_result, f, indent=2, ensure_ascii=False)

            all_results.append(full_result)
            success += 1

    # Résumé global
    print(f"\n{'='*70}")
    print("  RÉSUMÉ FINAL")
    print(f"{'='*70}")
    print(f"  Total    : {total} CV(s)")
    print(f"  ✅ Succès : {success}")
    print(f"  ❌ Échecs : {failed}")

    if success > 0:
        avg_competences = sum(
            len(r['parsing']['competences'])
            for r in all_results if 'parsing' in r
        ) / success
        print(f"  📊 Moy. compétences/CV : {avg_competences:.1f}")

    # Sauvegarder le rapport global
    rapport = OUTPUT_DIR / "rapport_batch.json"
    with open(rapport, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n  💾 Résultats sauvegardés dans : {OUTPUT_DIR.resolve()}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_all_cvs()
