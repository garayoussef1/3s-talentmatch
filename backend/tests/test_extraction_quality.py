"""
Script de validation de la qualité d'extraction des CVs
Teste les 3 types d'extraction avec des métriques de qualité

Usage:
    python -m pytest tests/test_extraction_quality.py -v -s
    OU
    python tests/test_extraction_quality.py (mode standalone)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from typing import Dict, List, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.extraction.cv_extractor import CVExtractor


@dataclass
class QualityMetrics:
    """Métriques de qualité d'extraction"""
    extraction_time: float  # Temps en secondes
    text_length: int        # Nombre de caractères extraits
    similarity_score: float # Score de similarité avec référence (0-1)
    success: bool
    method: str
    format: str
    key_fields_found: Dict[str, bool]  # Champs clés détectés
    error: str = None


class ExtractionQualityValidator:
    """Validateur de qualité d'extraction"""

    def __init__(self):
        self.extractor = CVExtractor(ocr_languages=['fr', 'en'])
        self.results: List[QualityMetrics] = []

    def _check_key_fields(self, text: str, expected_fields: Dict[str, str]) -> Dict[str, bool]:
        """
        Vérifie si les champs clés sont présents dans le texte extrait.
        
        Args:
            text: Texte extrait
            expected_fields: Dict {field_name: expected_value}
            
        Returns:
            Dict {field_name: found}
        """
        text_lower = text.lower()
        return {
            field: value.lower() in text_lower
            for field, value in expected_fields.items()
        }

    def _calculate_similarity(self, extracted: str, reference: str) -> float:
        """
        Calcule la similarité entre texte extrait et référence.
        Utilise SequenceMatcher (algorithme Ratcliff-Obershelp).
        
        Returns:
            Score entre 0 (aucune similarité) et 1 (identique)
        """
        if not extracted or not reference:
            return 0.0
        
        # Normaliser : minuscules, espaces multiples
        ext_norm = ' '.join(extracted.lower().split())
        ref_norm = ' '.join(reference.lower().split())
        
        return SequenceMatcher(None, ext_norm, ref_norm).ratio()

    def test_extraction(
        self,
        file_path: str,
        reference_text: str = None,
        expected_fields: Dict[str, str] = None
    ) -> QualityMetrics:
        """
        Teste l'extraction d'un fichier CV et calcule les métriques.
        
        Args:
            file_path: Chemin vers le fichier CV
            reference_text: Texte de référence pour calculer la similarité
            expected_fields: Champs clés attendus {nom: valeur}
        
        Returns:
            QualityMetrics avec toutes les métriques calculées
        """
        print(f"\n{'='*70}")
        print(f"Test: {Path(file_path).name}")
        print(f"{'='*70}")

        # Extraction avec mesure du temps
        start_time = time.time()
        result = self.extractor.extract(file_path)
        extraction_time = time.time() - start_time

        # Calcul des métriques
        text = result.get('text', '')
        text_length = len(text)
        
        # Similarité avec référence (si fournie)
        similarity = 0.0
        if reference_text:
            similarity = self._calculate_similarity(text, reference_text)
        
        # Détection des champs clés
        key_fields_found = {}
        if expected_fields:
            key_fields_found = self._check_key_fields(text, expected_fields)

        metrics = QualityMetrics(
            extraction_time=extraction_time,
            text_length=text_length,
            similarity_score=similarity,
            success=result.get('success', False),
            method=result.get('method', ''),
            format=result.get('format', ''),
            key_fields_found=key_fields_found,
            error=result.get('error')
        )

        # Affichage des résultats
        self._print_metrics(metrics, text[:500] if text else "")
        
        self.results.append(metrics)
        return metrics

    def _print_metrics(self, metrics: QualityMetrics, text_preview: str):
        """Affiche les métriques de manière lisible"""
        print(f"\n✅ Succès: {metrics.success}")
        print(f"⚙️  Méthode: {metrics.method}")
        print(f"📄 Format: {metrics.format}")
        print(f"⏱️  Temps extraction: {metrics.extraction_time:.3f}s")
        print(f"📝 Caractères extraits: {metrics.text_length}")
        
        if metrics.similarity_score > 0:
            print(f"🎯 Score similarité: {metrics.similarity_score:.2%}")
            self._print_quality_level(metrics.similarity_score)
        
        if metrics.key_fields_found:
            print(f"\n🔍 Champs clés détectés:")
            for field, found in metrics.key_fields_found.items():
                status = "✓" if found else "✗"
                print(f"   {status} {field}")
        
        if metrics.error:
            print(f"\n❌ Erreur: {metrics.error}")
        
        if text_preview:
            print(f"\n📄 Aperçu du texte extrait:")
            print(f"   {text_preview[:300]}...")

    def _print_quality_level(self, score: float):
        """Affiche le niveau de qualité selon le score"""
        if score >= 0.9:
            print("   → Excellente qualité ⭐⭐⭐⭐⭐")
        elif score >= 0.8:
            print("   → Très bonne qualité ⭐⭐⭐⭐")
        elif score >= 0.7:
            print("   → Bonne qualité ⭐⭐⭐")
        elif score >= 0.6:
            print("   → Qualité acceptable ⭐⭐")
        else:
            print("   → Qualité faible ⭐ - Amélioration nécessaire")

    def generate_summary_report(self):
        """Génère un rapport récapitulatif de tous les tests"""
        if not self.results:
            print("\nAucun test effectué.")
            return

        print(f"\n{'='*70}")
        print("RAPPORT DE QUALITÉ - RÉCAPITULATIF")
        print(f"{'='*70}")

        total = len(self.results)
        success_count = sum(1 for r in self.results if r.success)
        avg_time = sum(r.extraction_time for r in self.results) / total
        avg_similarity = sum(r.similarity_score for r in self.results) / total
        
        print(f"\n📊 Statistiques globales:")
        print(f"   Tests effectués: {total}")
        print(f"   Succès: {success_count}/{total} ({success_count/total:.0%})")
        print(f"   Temps moyen: {avg_time:.3f}s")
        
        if avg_similarity > 0:
            print(f"   Similarité moyenne: {avg_similarity:.2%}")
            self._print_quality_level(avg_similarity)

        print(f"\n📋 Détails par méthode:")
        methods = {}
        for result in self.results:
            method = result.method
            if method not in methods:
                methods[method] = []
            methods[method].append(result)
        
        for method, results in methods.items():
            avg_method_time = sum(r.extraction_time for r in results) / len(results)
            avg_method_sim = sum(r.similarity_score for r in results) / len(results) if results else 0
            print(f"\n   {method}:")
            print(f"      Nombre: {len(results)}")
            print(f"      Temps moyen: {avg_method_time:.3f}s")
            if avg_method_sim > 0:
                print(f"      Similarité moyenne: {avg_method_sim:.2%}")

        print(f"\n{'='*70}\n")


# ================================================================
# Tests automatisés avec pytest
# ================================================================

def test_pdf_text_extraction_quality():
    """Test qualité extraction PDF texte (avec fichier réel si disponible)"""
    validator = ExtractionQualityValidator()
    
    # Créer un PDF de test simple si disponible
    test_pdf = Path("data/cvs_raw/test_pdf_text.pdf")
    
    if not test_pdf.exists():
        print(f"\n⚠️  Fichier {test_pdf} non trouvé - test skippé")
        print("   💡 Créez un PDF texte dans data/cvs_raw/ pour tester")
        return
    
    expected_fields = {
        "nom": "dupont",
        "python": "python",
        "email": "@"
    }
    
    metrics = validator.test_extraction(
        str(test_pdf),
        expected_fields=expected_fields
    )
    
    assert metrics.success, "L'extraction PDF doit réussir"
    assert metrics.text_length > 50, "Le texte extrait doit contenir au moins 50 caractères"
    assert metrics.extraction_time < 5, "L'extraction doit prendre moins de 5 secondes"


def test_docx_extraction_quality():
    """Test qualité extraction DOCX (avec fichier réel si disponible)"""
    validator = ExtractionQualityValidator()
    
    test_docx = Path("data/cvs_raw/test_word.docx")
    
    if not test_docx.exists():
        print(f"\n⚠️  Fichier {test_docx} non trouvé - test skippé")
        print("   💡 Créez un DOCX dans data/cvs_raw/ pour tester")
        return
    
    expected_fields = {
        "nom": "martin",
        "competences": "competences",
    }
    
    metrics = validator.test_extraction(
        str(test_docx),
        expected_fields=expected_fields
    )
    
    assert metrics.success, "L'extraction DOCX doit réussir"
    assert metrics.text_length > 50, "Le texte extrait doit contenir au moins 50 caractères"
    assert metrics.extraction_time < 3, "L'extraction doit prendre moins de 3 secondes"


def test_ocr_extraction_quality():
    """Test qualité extraction OCR (PDF scanné)"""
    validator = ExtractionQualityValidator()
    
    # Utiliser le CV scanné créé précédemment
    test_scanned = Path("data/cvs_raw/scanned/cv_scanne_test.pdf")
    
    if not test_scanned.exists():
        print(f"\n⚠️  Fichier {test_scanned} non trouvé - test skippé")
        print("   💡 Un CV scanné est nécessaire pour ce test")
        return
    
    expected_fields = {
        "nom": "youssef",
        "python": "python",
        "fastapi": "fastapi",
        "experience": "experience"
    }
    
    reference = """
    CURRICULUM VITAE
    Nom: Youssef Test
    Email: youssef.test@example.com
    Telephone: +216 22 333 444
    Competences: Python, FastAPI, SQLAlchemy, PostgreSQL
    Experience: Developpeur Full Stack
    """
    
    metrics = validator.test_extraction(
        str(test_scanned),
        reference_text=reference,
        expected_fields=expected_fields
    )
    
    assert metrics.success, "L'extraction OCR doit réussir"
    assert metrics.text_length > 50, "Le texte OCR doit contenir au moins 50 caractères"
    # OCR est plus lent, donc timeout plus généreux
    assert metrics.extraction_time < 30, "L'extraction OCR doit prendre moins de 30 secondes"
    # Score de similarité acceptable pour OCR (peut avoir des erreurs)
    if metrics.similarity_score > 0:
        assert metrics.similarity_score > 0.5, "La similarité OCR doit être > 50%"


# ================================================================
# Mode standalone (exécution directe)
# ================================================================

if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║        TEST DE QUALITÉ D'EXTRACTION CVs - TalentMatch             ║
║                          Sprint 1                                 ║
╚═══════════════════════════════════════════════════════════════════╝
    """)

    validator = ExtractionQualityValidator()
    
    # Liste des fichiers de test à vérifier
    test_files = [
        ("data/cvs_raw/scanned/cv_scanne_test.pdf", {
            "nom": "youssef",
            "python": "python",
            "fastapi": "fastapi"
        }),
        ("data/cvs_raw/test_pdf_text.pdf", {
            "nom": "test",
            "python": "python"
        }),
        ("data/cvs_raw/test_word.docx", {
            "competences": "competences"
        })
    ]
    
    # Tester chaque fichier disponible
    for file_path, expected_fields in test_files:
        path = Path(file_path)
        if path.exists():
            validator.test_extraction(str(path), expected_fields=expected_fields)
        else:
            print(f"\n⚠️  {path.name} non trouvé - test skippé")
    
    # Rapport final
    validator.generate_summary_report()
    
    print("\n💡 Recommandations d'amélioration:")
    print("   1. Similarité < 70% → Vérifier la qualité du fichier source")
    print("   2. Temps > 10s (PDF/DOCX) → Optimiser le traitement")
    print("   3. Temps > 30s (OCR) → Réduire résolution ou taille image")
    print("   4. Champs manquants → Améliorer le format du CV source")
    print("   5. OCR imprécis → Utiliser images haute résolution (300+ DPI)")
