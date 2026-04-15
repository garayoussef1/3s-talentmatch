# Matching IA - Documentation Technique
# Projet : 3S TalentMatch - PFE ESPRIT 2025-2026
# Auteur  : Youssef Gara

---

## 1. Objectif

Construire un systeme de matching CV-offres progressif et defensable en soutenance,
sans casser le moteur de production existant.

Principes retenus :
- Sandbox isolee (aucune persistance en base).
- Garder le moteur officiel intact.
- Comparer heuristique vs ML vs IA semantique avec des metriques claires.

---

## 2. Architecture du systeme de matching

```
Offre d'emploi + CV candidat
         |
         v
+---------------------------+
|   MatchEngine             |  <- Production (non modifie)
|   (heuristique RapidFuzz) |
+---------------------------+
         |
         v
+---------------------------+
|   Sandbox (non destructif)|
|   - SandboxMLScorer       |  <- LogReg classique
|   - BERTMatchingScorer    |  <- Sentence-BERT (IA profonde)
+---------------------------+
         |
         v
POST /api/match-sandbox/{id}?engine=heuristic_ml|bert|compare_all
```

---

## 3. Moteurs implementes

### 3.1 MatchEngine - Heuristique (production)

Fichier : app/services/matching/match_engine.py

Composants :
- Skills : fuzzy matching RapidFuzz (token_set_ratio)
- Experience : ratio annees_candidat / annees_requises
- Education : comparaison niveau Bac+X
- Localisation : presence ville dans texte CV
- Semantique : similarite spaCy word vectors

Poids :
- Skills      : 45%
- Experience  : 25%
- Education   : 20%
- Localisation: 10%
- Semantique  : 12% (normalise)

### 3.2 SandboxMLScorer - Machine Learning classique

Fichier : app/services/matching_sandbox/ml_scorer.py

Modele : Logistic Regression (logreg_v1.joblib)
Dataset : 6 lignes (1 reel + 5 synthetiques bootstrap)
Statut  : PoC technique valide, pas encore productif (manque de donnees reelles)

### 3.3 BERTMatchingScorer - IA Semantique Profonde (NOUVEAU)

Fichier : app/services/matching_sandbox/bert_scorer.py

Modele : paraphrase-multilingual-MiniLM-L12-v2
Source : HuggingFace (sentence-transformers)
Taille : 3.4 GB sur disque
Langues: 50 langues dont FR et EN natif
Mode   : offline apres 1er telechargement (fonctionne sans internet)

Formule du score :
  total = 0.50 x bert_semantic
        + 0.30 x bert_skills
        + 0.20 x base
        - penalty

  bert_semantic : cosine similarity embeddings offre vs CV complet
  bert_skills   : max cosine sim par skill requise vs skills candidat
  base          : (exp_score + edu_score) / 2
  penalty       : min(0.15, nb_incoherences x 0.05)

Detection d'incoherences (4 niveaux) :
  Niveau 1 : skill declaree absente du texte brut du CV
  Niveau 2 : skill absente de toutes les descriptions d'experiences
  Niveau 3 : ecosysteme manquant (React sans JavaScript, Angular sans TypeScript...)
  Niveau 4 : similarite BERT entre skill et contexte experience < 0.25

---

## 4. Endpoint sandbox

Route : POST /api/match-sandbox/{job_offer_id}
Auth  : recruteur ou admin uniquement
Params:
  - alpha  : float (0-1, defaut 0.6) - poids ML dans hybride heuristic_ml
  - engine : string - mode de calcul

Modes disponibles :

  engine=heuristic_ml (defaut)
    Retourne : heuristic_score, ml_score, hybrid_score = alpha*ml + (1-alpha)*heuristic

  engine=bert
    Retourne : bert_score, details (semantic, skills, incoherences)

  engine=compare_all
    Retourne : heuristic_score, ml_score, bert_score,
               hybrid_score = 0.4*bert + 0.3*ml + 0.3*heuristic

Regles importantes :
  - persisted = False dans tous les modes (aucune ecriture en base)
  - /api/match (production) non modifie

---

## 5. Resultats de validation (demo sur CVs reels)

### 5.1 Configuration du test

Date      : 15 avril 2026
CVs testes: 6 CVs reels (Wajih EN/FR, Maram, Ines, Ahmed Aziz, Ranim EN)
Offres    : 3 offres fictives realistes

### 5.2 Offre : Ingenieur Backend Python
Skills requises : Python, FastAPI, Docker, SQL, REST API

Candidat        | Heuristique | BERT  | Diff  | Incoherences
----------------|-------------|-------|-------|-------------
Wajih EN        |    72.4%    | 65.4% |  -7%  | 2 (FastAPI, Docker absents)
Ahmed Aziz      |    63.5%    | 65.0% |  +1%  | 1
Maram           |    68.8%    | 63.5% |  -5%  | 2
Ranim EN        |    69.2%    | 62.9% |  -6%  | 2
Wajih FR        |    72.6%    | 60.9% | -12%  | 3
Ines            |    65.7%    | 56.2% |  -9%  | 5

BERT moyen : 62.3%  |  Heuristique moyen : 68.7%

### 5.3 Offre : Data Scientist / ML Engineer
Skills requises : Python, Machine Learning, TensorFlow, Pandas, Deep Learning

Candidat        | Heuristique | BERT  | Diff  | Incoherences
----------------|-------------|-------|-------|-------------
Wajih FR        |    75.0%    | 70.4% |  -5%  | 1
Wajih EN        |    74.1%    | 69.7% |  -4%  | 1
Ranim EN        |    71.9%    | 69.3% |  -3%  | 1
Ines            |    73.3%    | 68.9% |  -4%  | 1
Maram           |    87.9%    | 66.7% | -21%  | 5 (penalite max)
Ahmed Aziz      |    81.7%    | 60.2% | -22%  | 3

Observation : Maram declare TensorFlow/Pandas mais ces termes sont
peu presents dans ses experiences concretes -> BERT penalise correctement.

### 5.4 Offre : Developpeur Mobile React Native
Skills requises : React Native, JavaScript, TypeScript, Mobile, Git

Candidat        | Heuristique | BERT  | Diff  | Incoherences
----------------|-------------|-------|-------|-------------
Ines            |    80.6%    | 68.9% | -12%  | 2
Ahmed Aziz      |    73.4%    | 66.7% |  -7%  | 1
Wajih FR        |    81.1%    | 65.2% | -16%  | 2
Wajih EN        |    81.1%    | 65.1% | -16%  | 2
Maram           |    76.2%    | 64.1% | -12%  | 2
Ranim EN        |    84.1%    | 60.5% | -24%  | 3

Observation : Ines correctement classee #1 (profil mobile valide).

---

## 6. Analyse comparative heuristique vs BERT

Avantages de BERT sur l'heuristique :
1. Comprend le sens semantique : "Python engineer" = "developpeur Python"
2. Multilingue natif : compare FR et EN sans traduction
3. Detection d'incoherences : penalise les skills declarees mais non prouvees
4. Robuste aux variations de vocabulaire : "FastAPI" ~ "REST framework Python"

Limites actuelles :
1. Score BERT inferieur a l'heuristique en moyenne (-10%) a cause de la penalite
2. Penalite parfois agressive si le CV est court ou peu detaille
3. Temps de calcul : 1-3 sec par matching sur CPU (acceptable pour demo)
4. Modele generique : non fine-tune sur CVs tunisiens specifiquement

---

## 7. Tests automatises

Fichier : backend/tests/test_bert_matching.py
Nombre  : 3 tests pytest
Mode    : mock SentenceTransformer (pas de telechargement requis pour CI)

test_bert_semantic_score        : score [0,1] avec mock vecteurs fixes
test_skill_inconsistency_detection : Kubernetes absent du texte -> niveau 1 detecte
test_hybrid_scoring             : score total [0,1] avec candidat et offre mock

Execution : python -m pytest tests/test_bert_matching.py -v
Resultat  : 3/3 PASSED

---

## 8. Demo standalone

Fichier : demo_matching.py (racine du projet)
Usage   : .venv-10\Scripts\python.exe demo_matching.py

Aucune base de donnees requise.
Lit les CVs depuis data/Cv/ directement.
Affiche tableau comparatif heuristique vs BERT pour 3 offres types.

---

## 9. Ce qui reste a faire (ameliorations possibles)

Court terme :
- Calibrer les poids BERT (50/30/20) sur plus de CVs reels
- Ajouter plus d'ecosystemes dans la detection (Vue->JavaScript, Laravel->PHP)
- Afficher les scores BERT dans le frontend recruteur

Moyen terme :
- Collecter des labels reels (recruteur accepte/refuse) pour entrainer le ML
- Fine-tuning du modele BERT sur donnees metier tunisiennes
- Explication du score au recruteur ("Pourquoi 65% ?")

---

## 10. Conclusion

Le systeme de matching dispose maintenant de 3 niveaux d'intelligence :

Niveau 1 - Heuristique (production)
  Rapide, deterministe, explicable. Base de comparaison.

Niveau 2 - Machine Learning classique (sandbox)
  LogReg sur features extraites. Necessite plus de donnees reelles.

Niveau 3 - Sentence-BERT (sandbox IA)
  Comprehension semantique profonde. Multilingue FR+EN.
  Detecte les incoherences. Defensable en soutenance PFE.

Architecture sandbox garantit : aucun risque sur la production,
comparaison transparente, evolution progressive vers le meilleur moteur.
