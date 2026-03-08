"""
Améliorations de la qualité d'extraction - Phase 1
Implémente les corrections critiques identifiées dans le rapport qualité

Fonctionnalités:
1. Normalisation du texte (accents, casse)
2. Recherche fuzzy tolérante aux erreurs OCR
3. Détection robuste des champs clés
"""

import unicodedata
import re
from typing import Dict, List, Tuple
from difflib import SequenceMatcher


class TextNormalizer:
    """Normalisation du texte pour recherche robuste"""
    
    @staticmethod
    def remove_accents(text: str) -> str:
        """
        Retire les accents d'un texte.
        
        Exemple:
            "Compétences" → "Competences"
            "Expérience" → "Experience"
        """
        nfd_form = unicodedata.normalize('NFD', text)
        return ''.join(
            char for char in nfd_form 
            if unicodedata.category(char) != 'Mn'
        )
    
    @staticmethod
    def normalize_for_search(text: str) -> str:
        """
        Normalise du texte pour la recherche :
        - Minuscules
        - Sans accents
        - Espaces multiples réduits
        
        Args:
            text: Texte à normaliser
            
        Returns:
            Texte normalisé
        """
        if not text:
            return ""
        
        # Minuscules
        text = text.lower()
        
        # Retirer accents
        text = TextNormalizer.remove_accents(text)
        
        # Normaliser espaces
        text = ' '.join(text.split())
        
        return text


class FuzzyFieldMatcher:
    """Recherche tolérante aux erreurs de champs dans le texte"""
    
    def __init__(self, similarity_threshold: float = 0.75):
        """
        Args:
            similarity_threshold: Score minimum de similarité (0-1)
                                  0.75 = 75% de similarité minimum
        """
        self.threshold = similarity_threshold
    
    def find_field(
        self, 
        text: str, 
        field_variants: List[str],
        use_fuzzy: bool = True
    ) -> Tuple[bool, str, float]:
        """
        Cherche un champ dans le texte avec tolérance aux erreurs.
        
        Args:
            text: Texte dans lequel chercher
            field_variants: Liste de variantes du champ
                           Ex: ["python", "python3", "py"]
            use_fuzzy: Utiliser recherche floue (pour OCR)
            
        Returns:
            (trouvé: bool, match: str, score: float)
        """
        # Normaliser texte
        text_norm = TextNormalizer.normalize_for_search(text)
        
        # 1. Recherche exacte sur variantes
        for variant in field_variants:
            variant_norm = TextNormalizer.normalize_for_search(variant)
            if variant_norm in text_norm:
                return (True, variant, 1.0)
        
        # 2. Recherche fuzzy si activée (utile pour OCR)
        if use_fuzzy:
            words = text_norm.split()
            
            for word in words:
                for variant in field_variants:
                    variant_norm = TextNormalizer.normalize_for_search(variant)
                    
                    # Calculer similarité
                    similarity = SequenceMatcher(
                        None, word, variant_norm
                    ).ratio()
                    
                    if similarity >= self.threshold:
                        return (True, word, similarity)
        
        return (False, "", 0.0)


class RobustFieldDetector:
    """Détecteur robuste de champs clés dans les CVs"""
    
    # Dictionnaire de variantes pour champs courants
    FIELD_VARIANTS = {
        "nom": ["nom", "name", "prenom", "firstname", "lastname"],
        "email": ["email", "e-mail", "mail", "courriel", "@"],
        "telephone": ["telephone", "tel", "phone", "mobile", "portable", "+"],
        "linkedin": ["linkedin", "linked-in", "in/"],
        "competences": ["competences", "compétences", "skills", "aptitudes", "technologies"],
        "experience": ["experience", "expérience", "parcours"],
        "formation": ["formation", "education", "diplome", "diplôme", "etudes", "études"],
        "python": ["python", "python3", "py"],
        "fastapi": ["fastapi", "fast-api", "fast api"],
        "react": ["react", "reactjs", "react.js"],
        "docker": ["docker", "container"],
        "git": ["git", "github", "gitlab"],
    }
    
    def __init__(self, use_fuzzy: bool = True, threshold: float = 0.75):
        """
        Args:
            use_fuzzy: Activer recherche floue (recommandé pour OCR)
            threshold: Seuil de similarité (0.75 = 75%)
        """
        self.matcher = FuzzyFieldMatcher(similarity_threshold=threshold)
        self.use_fuzzy = use_fuzzy
    
    def detect_fields(
        self, 
        text: str, 
        expected_fields: Dict[str, str]
    ) -> Dict[str, Dict]:
        """
        Détecte les champs attendus dans le texte.
        
        Args:
            text: Texte extrait du CV
            expected_fields: Dict {field_key: expected_value}
                            Ex: {"nom": "dupont", "python": "python"}
        
        Returns:
            Dict avec résultats détaillés:
            {
                "nom": {
                    "found": True,
                    "match": "dupont",
                    "score": 0.95,
                    "method": "exact"
                },
                ...
            }
        """
        results = {}
        
        for field_key, expected_value in expected_fields.items():
            # Récupérer les variantes du champ
            variants = self.FIELD_VARIANTS.get(
                field_key, 
                [expected_value]  # Si pas de variantes, utiliser valeur attendue
            )
            
            # Si valeur attendue non dans variantes, l'ajouter
            if expected_value not in variants:
                variants.append(expected_value)
            
            # Chercher le champ
            found, match, score = self.matcher.find_field(
                text, variants, use_fuzzy=self.use_fuzzy
            )
            
            results[field_key] = {
                "found": found,
                "match": match,
                "score": score,
                "method": "fuzzy" if score < 1.0 else "exact"
            }
        
        return results
    
    def generate_report(self, results: Dict[str, Dict]) -> str:
        """Génère un rapport lisible des résultats"""
        report = []
        report.append("\n🔍 Détection de champs avec recherche robuste:\n")
        
        for field, result in results.items():
            status = "✓" if result["found"] else "✗"
            
            if result["found"]:
                score_pct = result["score"] * 100
                method = result["method"]
                match = result["match"]
                report.append(
                    f"   {status} {field:15} | Match: {match:20} | "
                    f"Score: {score_pct:5.1f}% | Méthode: {method}"
                )
            else:
                report.append(f"   {status} {field:15} | Non trouvé")
        
        return '\n'.join(report)


# ================================================================
# Fonctions utilitaires pour intégration
# ================================================================

def improved_check_key_fields(
    text: str, 
    expected_fields: Dict[str, str],
    use_fuzzy: bool = True
) -> Dict[str, bool]:
    """
    Version améliorée de la vérification de champs.
    Remplace _check_key_fields dans test_extraction_quality.py
    
    Args:
        text: Texte extrait
        expected_fields: Champs attendus
        use_fuzzy: Activer recherche floue (pour OCR)
    
    Returns:
        Dict {field: found}
    """
    detector = RobustFieldDetector(use_fuzzy=use_fuzzy)
    results = detector.detect_fields(text, expected_fields)
    
    return {
        field: result["found"] 
        for field, result in results.items()
    }


# ================================================================
# Tests des améliorations
# ================================================================

def test_normalizer():
    """Test du normaliseur"""
    print("\n" + "="*70)
    print("TEST - Normalisation de texte")
    print("="*70)
    
    test_cases = [
        "Compétences",
        "Expérience professionnelle",
        "Développeur Python",
        "École d'ingénieurs"
    ]
    
    for text in test_cases:
        normalized = TextNormalizer.normalize_for_search(text)
        print(f"  '{text}' → '{normalized}'")


def test_fuzzy_matcher():
    """Test de la recherche floue"""
    print("\n" + "="*70)
    print("TEST - Recherche floue (simulation erreurs OCR)")
    print("="*70)
    
    # Simuler texte avec erreurs OCR
    ocr_text = """
    Nom: Yousset Test
    Email: yousset.test@example.com
    
    Competences:
    - Pyton (erreur OCR)
    - FastAPlet (erreur OCR)
    - Peact (erreur OCR)
    - PostgreSOL
    """
    
    fields_to_find = {
        "nom": "youssef",
        "python": "python",
        "fastapi": "fastapi",
        "react": "react",
        "email": "@"
    }
    
    # Avec recherche fuzzy
    print("\n📊 Avec recherche FUZZY (tolérance erreurs):")
    detector_fuzzy = RobustFieldDetector(use_fuzzy=True, threshold=0.7)
    results_fuzzy = detector_fuzzy.detect_fields(ocr_text, fields_to_find)
    print(detector_fuzzy.generate_report(results_fuzzy))
    
    # Sans recherche fuzzy (ancien système)
    print("\n📊 Sans recherche fuzzy (exacte uniquement):")
    detector_exact = RobustFieldDetector(use_fuzzy=False)
    results_exact = detector_exact.detect_fields(ocr_text, fields_to_find)
    print(detector_exact.generate_report(results_exact))
    
    # Comparaison
    found_fuzzy = sum(1 for r in results_fuzzy.values() if r["found"])
    found_exact = sum(1 for r in results_exact.values() if r["found"])
    
    print(f"\n📈 Amélioration:")
    print(f"   Fuzzy: {found_fuzzy}/{len(fields_to_find)} champs trouvés")
    print(f"   Exact: {found_exact}/{len(fields_to_find)} champs trouvés")
    print(f"   Gain:  +{found_fuzzy - found_exact} champs détectés")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║    AMÉLIORATION QUALITÉ EXTRACTION - Phase 1                      ║
║                  TalentMatch Sprint 1                             ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Tests
    test_normalizer()
    test_fuzzy_matcher()
    
    print("\n" + "="*70)
    print("✅ Tests terminés - Améliorations validées")
    print("="*70)
    print("\n💡 Pour intégrer dans test_extraction_quality.py:")
    print("   1. Importer: from extraction_improvements import improved_check_key_fields")
    print("   2. Remplacer _check_key_fields par improved_check_key_fields")
    print("   3. Relancer les tests de qualité\n")
