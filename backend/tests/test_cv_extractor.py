"""
Test de l'extracteur unifié CVExtractor
Teste les 3 formats en une seule commande
Partie du projet 3S TalentMatch
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.cv_extractor import CVExtractor


def test_cv(file_path: str, extractor: CVExtractor = None):
    if extractor is None:
        extractor = CVExtractor()

    print(f"\n{'─'*70}")
    print(f"Fichier : {Path(file_path).name}")
    print(f"{'─'*70}")

    result = extractor.extract(file_path)

    status = "✓ SUCCÈS" if result['success'] else "❌ ÉCHEC"
    print(f"{status}")
    print(f"  Format  : {result['format']}")
    print(f"  Méthode : {result['method']}")
    print(f"  Pages   : {result['pages']}")
    print(f"  Texte   : {len(result['text'])} caractères")

    if result['success']:
        print(f"  Aperçu  : {result['text'][:120].replace(chr(10), ' ')}")
    else:
        print(f"  Erreur  : {result['error']}")

    return result


def main():
    print("\n╔" + "═"*68 + "╗")
    print("║" + " "*16 + "3S TALENTMATCH - TEST EXTRACTEUR UNIFIÉ" + " "*13 + "║")
    print("╚" + "═"*68 + "╝")

    # Un seul extracteur pour tous les formats
    extractor = CVExtractor()

    print("\nQuel test voulez-vous lancer ?")
    print("  1. Tester les 3 formats automatiquement (pdf + docx + image)")
    print("  2. Tester un fichier spécifique")
    print("  3. Test format non supporté")

    choice = input("\nVotre choix (1/2/3): ").strip()

    if choice == "1":
        print("\n" + "="*70)
        print("TEST AUTOMATIQUE - 3 FORMATS")
        print("="*70)

        files = [
            r"..\data\cvs_raw\templates\asma.pdf",
            r"..\data\cvs_raw\word\asma.docx",
            r"..\data\cvs_raw\scanned\asma_scanned.png",
        ]

        results = [test_cv(f, extractor) for f in files]

        successes = sum(1 for r in results if r['success'])
        print(f"\n{'='*70}")
        print(f"RÉSULTAT FINAL : {successes}/{len(results)} extractions réussies")
        print(f"{'='*70}")

    elif choice == "2":
        path = input("Chemin vers le fichier: ").strip()
        test_cv(path, extractor)

    elif choice == "3":
        test_cv("document.txt", extractor)

    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    main()
