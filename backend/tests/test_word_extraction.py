"""
Tests pour l'extraction de CVs Word (.docx)
Partie du projet 3S TalentMatch
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.word_extractor import WordExtractor


def test_single_word_cv(cv_path: str):
    print("\n" + "="*70)
    print(f"TEST EXTRACTION WORD: {Path(cv_path).name}")
    print("="*70)

    extractor = WordExtractor()
    result = extractor.extract(cv_path)

    print(f"\n✓ Succès: {result['success']}")
    print(f"✓ Méthode: {result['method']}")
    print(f"✓ Longueur texte: {len(result['text'])} caractères")

    if result['success']:
        print(f"\n{'─'*70}")
        print("APERÇU DU TEXTE EXTRAIT (500 premiers caractères):")
        print(f"{'─'*70}")
        print(result['text'][:500])
        print(f"{'─'*70}")
    else:
        print(f"\n❌ ERREUR: {result['error']}")

    print("="*70)
    return result


def main():
    print("\n╔" + "═"*68 + "╗")
    print("║" + " "*18 + "3S TALENTMATCH - TESTS EXTRACTION WORD" + " "*12 + "║")
    print("╚" + "═"*68 + "╝")

    print("\nQuel test voulez-vous lancer ?")
    print("  1. Test sur un seul CV Word")
    print("  2. Test batch sur un dossier")
    print("  3. Test rapide (fichier inexistant)")

    choice = input("\nVotre choix (1/2/3): ").strip()

    if choice == "1":
        cv_path = input("Chemin vers le CV (.docx): ").strip()
        test_single_word_cv(cv_path)

    elif choice == "2":
        cv_dir = input("Chemin vers le dossier: ").strip() or r"..\data\cvs_raw\word"
        dir_path = Path(cv_dir)
        if not dir_path.exists():
            print(f"❌ Dossier non trouvé: {cv_dir}")
            return
        docx_files = list(dir_path.glob("*.docx"))
        if not docx_files:
            print(f"❌ Aucun .docx trouvé dans: {cv_dir}")
            return
        for f in docx_files:
            test_single_word_cv(str(f))

    elif choice == "3":
        test_single_word_cv("fichier_inexistant.docx")

    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    main()
