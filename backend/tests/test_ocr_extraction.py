"""
Tests pour l'extraction OCR (PDFs scannés / images)
Partie du projet 3S TalentMatch
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.ocr_extractor import OCRExtractor


def test_single_image(file_path: str, languages: list = None):
    print("\n" + "="*70)
    print(f"TEST OCR: {Path(file_path).name}")
    print("="*70)

    extractor = OCRExtractor(languages=languages or ['fr', 'en'])
    result = extractor.extract(file_path)

    print(f"\n✓ Succès    : {result['success']}")
    print(f"✓ Méthode   : {result['method']}")
    print(f"✓ Pages     : {result['pages']}")
    print(f"✓ Caractères: {len(result['text'])}")

    if result['success']:
        print(f"\n{'─'*70}")
        print("TEXTE EXTRAIT PAR OCR:")
        print(f"{'─'*70}")
        print(result['text'][:800])
        print(f"{'─'*70}")
    else:
        print(f"\n❌ ERREUR: {result['error']}")

    print("="*70)
    return result


def main():
    print("\n╔" + "═"*68 + "╗")
    print("║" + " "*19 + "3S TALENTMATCH - TESTS EXTRACTION OCR" + " "*12 + "║")
    print("╚" + "═"*68 + "╝")

    print("\nQuel test voulez-vous lancer ?")
    print("  1. Test sur une image (.png / .jpg)")
    print("  2. Test sur un PDF scanné")
    print("  3. Test batch sur le dossier scanned/")
    print("  4. Test rapide (fichier inexistant)")

    choice = input("\nVotre choix (1/2/3/4): ").strip()

    if choice == "1":
        path = input("Chemin vers l'image: ").strip()
        test_single_image(path)

    elif choice == "2":
        path = input("Chemin vers le PDF scanné: ").strip()
        test_single_image(path)

    elif choice == "3":
        cv_dir = Path(r"..\data\cvs_raw\scanned")
        if not cv_dir.exists():
            print(f"❌ Dossier non trouvé: {cv_dir}")
            return
        files = list(cv_dir.glob("*.pdf")) + list(cv_dir.glob("*.png")) + list(cv_dir.glob("*.jpg"))
        if not files:
            print("❌ Aucun fichier trouvé dans scanned/")
            return
        for f in files:
            test_single_image(str(f))

    elif choice == "4":
        test_single_image("fichier_inexistant.png")

    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    main()
