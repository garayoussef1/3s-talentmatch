"""
Tests pour l'extraction de CVs PDF
Partie du projet 3S TalentMatch
"""

import sys
from pathlib import Path

# Ajouter le dossier parent au path Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.pdf_extractor import PDFExtractor


def test_single_cv(cv_path: str):
    """
    Teste l'extraction sur un seul CV
    
    Args:
        cv_path: Chemin vers le CV à tester
    """
    print("\n" + "="*70)
    print(f"TEST EXTRACTION: {Path(cv_path).name}")
    print("="*70)
    
    # Créer extracteur
    extractor = PDFExtractor()
    
    # Extraire
    result = extractor.extract(cv_path)
    
    # Afficher résultats
    print(f"\n✓ Succès: {result['success']}")
    print(f"✓ Méthode: {result['method']}")
    print(f"✓ Nombre de pages: {result['pages']}")
    print(f"✓ Longueur texte: {len(result['text'])} caractères")
    
    if result.get('needs_ocr'):
        print(f"⚠️  OCR nécessaire: {result['needs_ocr']}")
    
    if result['success']:
        print(f"\n{'─'*70}")
        print("APERÇU DU TEXTE EXTRAIT (500 premiers caractères):")
        print(f"{'─'*70}")
        print(result['text'][:500])
        print("...")
        print(f"{'─'*70}")
    else:
        print(f"\n❌ ERREUR: {result['error']}")
    
    print("="*70)
    
    return result


def test_multiple_cvs(cv_directory: str):
    """
    Teste l'extraction sur tous les CVs d'un dossier
    
    Args:
        cv_directory: Chemin vers le dossier contenant les CVs
    """
    cv_dir = Path(cv_directory)
    
    if not cv_dir.exists():
        print(f"❌ Dossier non trouvé: {cv_directory}")
        return
    
    # Trouver tous les PDFs
    pdf_files = list(cv_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ Aucun PDF trouvé dans: {cv_directory}")
        return
    
    print("\n" + "="*70)
    print(f"TEST BATCH: {len(pdf_files)} CV(s) trouvé(s)")
    print("="*70)
    
    extractor = PDFExtractor()
    results = []
    
    # Tester chaque CV
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] {pdf_file.name}...")
        result = extractor.extract(str(pdf_file))
        
        results.append({
            'filename': pdf_file.name,
            'success': result['success'],
            'pages': result['pages'],
            'chars': len(result['text']),
            'needs_ocr': result.get('needs_ocr', False)
        })
        
        # Affichage compact
        if result['success']:
            print(f"     ✓ OK - {result['pages']} page(s), {len(result['text'])} chars")
        else:
            print(f"     ❌ ÉCHEC - {result['error']}")
    
    # Résumé
    print("\n" + "="*70)
    print("RÉSUMÉ")
    print("="*70)
    
    successes = sum(1 for r in results if r['success'])
    failures = len(results) - successes
    ocr_needed = sum(1 for r in results if r.get('needs_ocr'))
    
    print(f"\n✓ Succès: {successes}/{len(results)} ({successes/len(results)*100:.1f}%)")
    print(f"❌ Échecs: {failures}/{len(results)}")
    print(f"⚠️  OCR nécessaire: {ocr_needed}/{len(results)}")
    
    if successes > 0:
        avg_chars = sum(r['chars'] for r in results if r['success']) / successes
        print(f"\n📊 Moyenne caractères extraits: {avg_chars:.0f}")
    
    print("\n" + "="*70)
    
    return results


def main():
    """Point d'entrée principal des tests"""
    
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*20 + "3S TALENTMATCH - TESTS EXTRACTION" + " "*15 + "║")
    print("╚" + "═"*68 + "╝")
    
    # Choix du test
    print("\nQuel test voulez-vous lancer ?")
    print("  1. Test sur un seul CV")
    print("  2. Test batch sur un dossier")
    print("  3. Test rapide (fichier inexistant)")
    
    choice = input("\nVotre choix (1/2/3): ").strip()
    
    if choice == "1":
        cv_path = input("Chemin vers le CV: ").strip()
        test_single_cv(cv_path)
    
    elif choice == "2":
        cv_dir = input("Chemin vers le dossier: ").strip() or "../../data/cvs_raw/templates"
        test_multiple_cvs(cv_dir)
    
    elif choice == "3":
        print("\nTest rapide: fichier inexistant")
        test_single_cv("fichier_qui_nexiste_pas.pdf")
    
    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    # Vous pouvez aussi appeler directement les fonctions
    # Par exemple:
    # test_single_cv("../../data/cvs_raw/templates/cv_001.pdf")
    # test_multiple_cvs("../../data/cvs_raw/templates")
    
    main()