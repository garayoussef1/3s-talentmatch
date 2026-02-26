"""Test du parser CV"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.cv_parser import CVParser


def test_full_pipeline(cv_path: str):
    """Pipeline complet : Extraction → Parsing"""
    
    print("\n" + "="*70)
    print("PIPELINE COMPLET : EXTRACTION → PARSING NLP")
    print("="*70)
    
    # 1. Extraction texte
    print("\n[1/2] Extraction texte...")
    extractor = CVExtractor()
    result = extractor.extract(cv_path)
    
    if not result['success']:
        print(f"❌ Échec extraction: {result['error']}")
        return
    
    text = result['text']
    print(f"✓ Texte extrait: {len(text)} caractères")
    
    # 2. Parsing NLP
    print("\n[2/2] Parsing NLP...")
    parser = CVParser()
    cv_data = parser.parse(text)
    
    # Affichage résultats
    print("\n" + "─"*70)
    print("RÉSULTAT STRUCTURÉ JSON")
    print("─"*70)
    
    print(f"\n👤 IDENTITÉ:")
    print(f"   Nom: {cv_data['identite']['nom_complet']}")
    
    print(f"\n📧 CONTACTS:")
    for key, value in cv_data['contacts'].items():
        if value:
            print(f"   {key}: {value}")
    
    print(f"\n💻 COMPÉTENCES ({len(cv_data['competences'])}):")
    for skill in cv_data['competences'][:15]:
        print(f"   • {skill}")
    
    print(f"\n🏢 EXPÉRIENCES ({len(cv_data['experiences'])}):")
    for exp in cv_data['experiences'][:3]:
        print(f"   • {exp['entreprise']}")
    
    print(f"\n🎓 FORMATIONS ({len(cv_data['formations'])}):")
    for edu in cv_data['formations'][:3]:
        print(f"   • {edu['diplome'][:60]}...")
    
    print(f"\n🌍 LANGUES ({len(cv_data['langues'])}):")
    if cv_data['langues']:
        print(f"   {', '.join(cv_data['langues'])}")
    else:
        print("   Aucune détectée")
    
    print(f"\n📊 STATISTIQUES:")
    print(f"   Mots: {cv_data['stats']['nb_mots']}")
    print(f"   Compétences: {cv_data['stats']['nb_competences']}")
    print(f"   Expériences: {cv_data['stats']['nb_experiences']}")
    
    print("\n" + "─"*70)
    print("JSON COMPLET:")
    print("─"*70)
    print(json.dumps(cv_data, indent=2, ensure_ascii=False))
    
    print("\n" + "="*70)
    
    return cv_data


if __name__ == "__main__":
    print("\n╔" + "═"*68 + "╗")
    print("║" + " "*20 + "TEST PARSER CV - 3S TALENTMATCH" + " "*17 + "║")
    print("╚" + "═"*68 + "╝")
    
    cv_path = input("\nChemin vers le CV: ").strip()
    cv_data = test_full_pipeline(cv_path)
    
    # Sauvegarder le résultat JSON
    if cv_data:
        output_path = Path(__file__).parent.parent / "data" / "cvs_processed" / "result_nlp.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(cv_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Résultat sauvegardé dans : {output_path}")
