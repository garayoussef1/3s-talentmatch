# Module d'Évaluation Technique — Rapport détaillé
### Plateforme 3S TalentMatch · PFE Youssef Gara · Juillet 2026

---

# PARTIE 1 — Explication simple (pour tous)

## 1.1 À quoi ça sert ?

Un CV **déclare** des compétences, mais rien ne prouve que le candidat les **maîtrise vraiment**.
Le module d'évaluation fait passer au candidat un **entretien technique automatisé** qui mesure
son niveau réel, puis compare ce niveau à ce que son CV annonce.

> **En une phrase :** le CV dit « Expert Python » — l'évaluation vérifie si c'est vrai.

## 1.2 Le parcours en 6 étapes

```
1. Le RECRUTEUR sélectionne un ou plusieurs candidats après le matching
   (+ il peut ajouter ses propres questions, et fixer une date d'ouverture
    et une date limite)
        ↓  (clic instantané)
2. L'IA LOCALE prépare le questionnaire de l'offre en arrière-plan
   (une seule fois par offre, ~5-8 min ; réutilisé ensuite)
        ↓
3. Le CANDIDAT reçoit un EMAIL professionnel : lien personnel + code PIN
   à usage unique + dates de passage
        ↓
4. Il se CONNECTE à son compte, saisit le PIN, lit les RÈGLES,
   puis passe le test en plein écran :
      • ~10 QCM dont la difficulté S'ADAPTE à ses réponses (90 s chacun)
      • 3 questions de RAISONNEMENT à rédiger (mises en situation)
      • les questions du recruteur
        ↓
5. L'IA LOCALE note tout : niveau par compétence, qualité du raisonnement,
   écart entre le CV déclaré et le niveau démontré (« Reality Gap »)
        ↓
6. Le RECRUTEUR consulte dans l'onglet « 🎯 Évaluations » :
      • le niveau démontré /10 et la cohérence CV ↔ test
      • le radar « Déclaré vs Démontré » par compétence
      • le rapport rédigé par l'IA (verdict argumenté)
      • toutes les réponses du candidat (pour vérifier lui-même)
      • le score d'intégrité (signaux anti-triche)
```

## 1.3 Ce qui rend ce module intelligent (pas un simple quiz)

| Aspect | Quiz classique | Notre module |
|---|---|---|
| Questions | Banque figée, écrites à la main | **Générées par IA** à partir des compétences de l'offre — fonctionne pour **tout domaine** (IT, finance, santé, droit…) sans écrire une question |
| Difficulté | Identique pour tous | **Adaptative (IRT)** : monte si le candidat réussit, descend s'il échoue → converge vers son vrai niveau en ~10 questions |
| Réponses rédigées | Non notées ou par mots-clés | Notées **au sens** par un modèle d'IA sémantique (BGE-M3) |
| Triche | Mêmes questions pour tous | Chaque candidat reçoit un **sous-ensemble différent**, options **mélangées**, timer, télémétrie |
| Résultat | Une note brute | Niveau par compétence + **écart avec le CV** + rapport IA + réponses vérifiables |

---

# PARTIE 2 — Fonctionnement technique détaillé

## 2.1 Architecture (fichiers principaux)

```
backend/app/
├── routes/assessment.py            ← tous les endpoints (20 routes)
├── services/assessment/
│   ├── llm_client.py               ← client Ollama LOCAL (aucune API externe)
│   ├── question_generator.py       ← génération des questions (paliers + auto-vérif)
│   ├── question_bank.py            ← pool par offre, génération en arrière-plan
│   ├── cat_engine.py               ← moteur IRT/CAT (catsim)
│   ├── semantic_scorer.py          ← notation sémantique (BGE-M3, cosinus)
│   ├── reality_gap.py              ← écart déclaré CV vs démontré
│   └── report_generator.py         ← rapport IA (Ollama)
├── models/assessment.py            ← 4 tables SQLAlchemy
frontend/src/
├── components/AssessmentPanel.jsx  ← lancement recruteur (multi-candidats, dates, questions perso)
├── components/AssessmentsTab.jsx   ← onglet 🎯 Évaluations (liste, radar, rapport, réponses)
├── pages/AssessmentCandidate.jsx   ← passage du test (PIN, règles, QCM, rédaction)
└── pages/MyAssessments.jsx         ← espace candidat « Mes Évaluations »
```

**Tables PostgreSQL :**

| Table | Contenu |
|---|---|
| `assessment_questions` | Pool de QCM par offre (question, 4 options, bonne réponse, difficulté 1-10, paramètre IRT) |
| `open_questions` | Questions de raisonnement par offre + 3 réponses de référence + leurs embeddings BGE-M3 |
| `assessment_sessions` | Une session par candidat : jeton d'accès, PIN, dates, questionnaire tiré (session_qcm / session_open), réponses, theta, scores, signaux d'intégrité |
| `reality_gap_results` | Écart déclaré/démontré par compétence, cohérence CV, score ajusté |

## 2.2 Génération des questions (100 % locale)

**Modèle utilisé :** Mistral 7B via **Ollama** (serveur local `http://localhost:11434`).

**Déclenchement :** au premier lancement d'une évaluation sur une offre, une tâche
d'**arrière-plan** (FastAPI `BackgroundTasks`) génère le pool de l'offre (~18 QCM + 6
questions rédigées). Le recruteur n'attend pas (lancement en 0,2 s) ; le candidat qui
ouvre trop tôt voit « questionnaire en préparation » avec rafraîchissement automatique.
Les lancements suivants sur la même offre sont immédiats (pool réutilisé).

**Ce que reçoit le LLM :** UNIQUEMENT le **titre du poste** et les **noms des
compétences requises** de l'offre (informations publiques). **Jamais le CV ni aucune
donnée du candidat.**

**Qualité (3 mécanismes) :**
1. **Génération par paliers** : 2 appels séparés — moitié « fondamentaux » (difficulté
   2-5), moitié « difficile/expert » (7-10 : pièges, cas limites) → des questions dures
   garanties.
2. **Distracteurs plausibles imposés** : les 4 options doivent être proches, de même
   forme ; les mauvaises options = erreurs fréquentes du métier → deviner au hasard ne
   donne aucun indice.
3. **Auto-vérification** : le LLM **répond lui-même** à chaque QCM généré **sans voir**
   la réponse marquée ; en cas de désaccord, la question est **rejetée** (filtre
   anti-erreur du modèle).

## 2.3 Le test adaptatif (IRT / CAT)

**Théorie :** *Item Response Theory* — le standard des tests standardisés (GMAT, TOEFL).
Librairie : `catsim`.

- Chaque question a des paramètres IRT : difficulté `b` (mappée de 1-10 vers l'échelle
  [-3, +3]), discrimination `a`, pseudo-chance `c = 0,25` (4 options).
- Le niveau du candidat est une variable **theta** (θ), initialisée à 0 (niveau moyen).
- À chaque réponse : θ est **ré-estimé** par maximum de vraisemblance
  (`NumericalSearchEstimator`), puis la question suivante est choisie parmi les plus
  **informatives** au niveau θ courant (`RandomesqueSelector`, qui tire au hasard parmi
  les 5 meilleures → deux candidats de même niveau ne voient pas les mêmes questions).
- Le test s'arrête à ~10 questions ; θ est converti en **niveau 0-10**, et un niveau
  par **compétence** est calculé (somme des difficultés réussies / posées × 10).

**Pourquoi IRT plutôt qu'un pourcentage ?** Un pourcentage dépend des questions posées
(un 8/10 sur des questions faciles ≠ un 8/10 sur des dures). θ estime le niveau
**indépendamment** des questions, ce qui permet le test court ET la comparaison
équitable entre candidats.

## 2.4 Notation des réponses rédigées (sémantique)

**Modèle :** BGE-M3 (le même modèle d'embeddings que le moteur de matching — instance
partagée, pas de double chargement).

Pour chaque question rédigée, le générateur a produit **3 réponses de référence** :
*faible* (vague), *correcte* (basique), *experte* (structurée). Leurs embeddings sont
pré-calculés et stockés.

À la soumission :
1. La réponse du candidat est encodée en vecteur (BGE-M3, local).
2. Similarité **cosinus** avec chacune des 3 références.
3. Score 0-100 par interpolation **softmax** vers les ancres 25 / 62 / 95 (la référence
   la plus proche domine).
4. Pénalité ×0,6 si la réponse fait moins de 30 mots.

→ On note le **sens** de la réponse, pas des mots-clés. Validation expérimentale :
réponse experte ≈ 80, correcte ≈ 41, faible ≈ 16, hors-sujet ≈ 31 (ordre respecté).

**Questions du recruteur :** posées au candidat dans le même flux, mais **non notées
par l'IA** — le recruteur les juge lui-même à la lecture (choix assumé : ce sont
souvent des questions de motivation sans « bonne réponse »).

## 2.5 Le « Reality Gap » (écart CV ↔ démontré)

1. **Niveau déclaré (0-10)** dérivé du CV parsé, par compétence, avec une formule
   transparente : base 5 si la compétence est listée, +0,4/année d'expérience indiquée
   (plafond +3), +2 si utilisée dans une expérience réelle, bonus séniorité
   (+1 confirmé, +2 senior). Compétence absente du CV → 0.
2. **Écart** : `gap = |déclaré − démontré| / 10` par compétence, moyenne **pondérée**
   par l'importance dans l'offre (requise = 1,0 ; appréciée = 0,5).
3. **Cohérence CV** : `100 − gap × 100` → seuils : ≥ 85 « CV cohérent », 70-85
   « à vérifier », < 70 « CV ≠ niveau démontré ».
4. **Score final ajusté** : `score_matching × (0,7 + 0,3 × cohérence/100)` — le
   matching reste dominant, la cohérence module.

Affichage : **radar superposé « Déclaré (CV) vs Démontré (test) »** par compétence
(Recharts) — le recruteur voit d'un coup d'œil quelles compétences sont surévaluées.

## 2.6 Le rapport IA

Principe clé : **le code calcule tous les chiffres** (θ, niveaux, scores, gap — aucun
risque d'hallucination), **l'IA locale rédige l'analyse qualitative** à partir de ces
chiffres et des réponses écrites : synthèse, niveau technique, qualité du raisonnement,
cohérence CV, verdict (RECRUTER / À APPROFONDIR / REJETER) justifié.

Le recruteur peut **tout vérifier** : bouton « Voir les réponses » → chaque QCM (choix
du candidat vs bonne réponse ✓/✗) et chaque rédaction avec son score.

## 2.7 Sécurité et anti-triche

**Contrôle d'accès (3 verrous successifs) :**
1. **Compte** : le candidat doit être connecté à SON compte (celui lié au CV) ;
   un admin/recruteur connecté peut aussi ouvrir le lien (test/aperçu).
2. **PIN** : code 6 chiffres à usage unique envoyé par email, exigé au démarrage et
   revalidé côté serveur à chaque réponse.
3. **Fenêtre de dates** : avant l'ouverture → « pas encore ouverte » ; après la
   limite → « clôturée » (réponses refusées, HTTP 403).

**Anti-triche (traçabilité, pas de sanction automatique) :**

| Signal | Détection |
|---|---|
| Questions partagées entre candidats | Impossible : sous-ensemble aléatoire par candidat + **options mélangées** (permutation déterministe par session, remappée côté serveur) |
| Recherche externe pendant un QCM | **Timer 90 s** par question (temps écoulé = compté faux) + temps de réponse enregistré (QCM difficile réussi < 5 s = signalé) |
| Copier-coller (ChatGPT…) | Bloqué sur questions ET réponses ; tentatives comptées |
| Texte injecté sans taper | **Télémétrie clavier** : frappes comptées vs longueur du texte (texte long avec très peu de frappes = injection signalée) |
| Sortie de l'écran du test | Plein écran obligatoire (annoncé sur l'écran des **règles**, accepté par le candidat avant de commencer) ; chaque sortie et chaque changement d'onglet est enregistré |

Tous ces signaux alimentent un **score d'intégrité (0-100)** présenté au recruteur avec
la liste des incidents. **Choix de conception assumé** : on ne bloque jamais le candidat
automatiquement (un F5 ou un Échap ne prouvent pas la triche) — on **trace et on
signale**, la décision reste **humaine**. C'est le modèle des outils de surveillance
d'examen professionnels, et c'est aussi la position la plus défendable juridiquement.

---

# PARTIE 3 — Internet, confidentialité et RGPD

## 3.1 Qu'est-ce qui utilise Internet ? (audit exact du code)

| Composant | Où ça tourne | Internet ? |
|---|---|---|
| Génération des questions (Mistral 7B) | **Ollama, sur la machine** (localhost:11434) | ❌ Non |
| Notation sémantique (BGE-M3) | **En mémoire, sur la machine** | ❌ Non |
| Test adaptatif (catsim) | **Bibliothèque Python locale** | ❌ Non |
| Rapport IA | **Ollama, sur la machine** | ❌ Non |
| Base de données | **PostgreSQL local** | ❌ Non |
| **Envoi des emails d'invitation** | SMTP (Gmail actuellement) | ✅ **Oui — seul flux sortant** |

**Le seul flux qui sort de la machine est l'email d'invitation**, qui contient :
l'adresse email du candidat, son prénom, le titre du poste, le lien, le PIN et les
dates. **Aucun contenu de CV, aucune réponse, aucun résultat ne sort jamais.**

> Recommandation production : remplacer le SMTP Gmail par le **serveur mail interne de
> l'entreprise** (une variable d'environnement à changer, zéro code).

À noter : le module d'entretien initial reposait sur une API cloud (Groq) ; il a été
**entièrement supprimé** du projet (code, tables, clé API) précisément pour respecter
l'interdiction des API externes. On peut le prouver : `grep -ri groq backend/` → 0 résultat.

## 3.2 Analyse RGPD (points de conformité)

| Principe RGPD | Comment le module y répond |
|---|---|
| **Minimisation des données** | Le LLM ne reçoit **que le titre du poste et les noms des compétences de l'offre** — jamais le CV, jamais l'identité. Le rapport IA ne reçoit que les résultats chiffrés et les réponses écrites, en local. |
| **Pas de transfert hors UE / hors machine** | Tout le traitement IA est local (Ollama + BGE-M3). Aucune donnée candidat n'est envoyée à un tiers. |
| **Information préalable** | Écran des **règles** avant le test : le candidat est informé (plein écran, enregistrement des sorties/onglets, analyse du clavier, timer) et **clique pour accepter** avant de commencer. |
| **Proportionnalité de la surveillance** | Pas de webcam, pas de micro, pas de capture d'écran — uniquement des signaux techniques (focus, frappe, temps), et **aucune décision automatique** : un humain juge. |
| **Décision non automatisée (art. 22)** | Le système **assiste** : le rapport est un outil d'aide à la décision ; le recruteur peut consulter toutes les réponses brutes et décide seul. |
| **Droit d'accès / effacement** | Les réponses sont consultables ; le recruteur peut **supprimer** une évaluation (bouton 🗑, suppression en cascade session + résultats). |
| **Sécurité d'accès** | Triple verrou (compte + PIN à usage unique + fenêtre de dates) ; endpoints recruteur protégés par authentification et rôle. |

**Points restant à formaliser pour une mise en production** (côté entreprise, pas côté code) :
- définir une **durée de conservation** des sessions/résultats (ex. purge à 12 mois) ;
- mentionner l'évaluation dans la **politique de confidentialité** de la plateforme ;
- SMTP interne (cf. ci-dessus).

## 3.3 Réponses aux questions probables de l'encadrante

**« Pourquoi l'IRT plutôt qu'un simple score ? »**
Parce que le niveau estimé est indépendant des questions posées : test plus court
(~10 questions), équitable entre candidats, et c'est la méthode des tests standardisés.

**« Comment garantissez-vous la qualité des questions générées ? »**
Trois garde-fous : paliers de difficulté imposés, distracteurs plausibles obligatoires,
et auto-vérification (le modèle répond à ses propres questions à l'aveugle ; désaccord
= question rejetée). En dernier ressort, le recruteur voit toutes les questions et peut
ignorer celles qu'il juge mauvaises — et le modèle local est remplaçable par un plus
performant (une variable d'environnement) sans changer le code.

**« Et si le candidat triche ? »**
On rend la triche difficile (questions uniques, options mélangées, timer, copier-coller
bloqué), on la rend détectable (télémétrie clavier, temps de réponse, sorties d'écran)
et on la rend visible (score d'intégrité + incidents dans le rapport). La sanction
reste humaine — c'est un choix éthique et juridique.

**« Quelles données personnelles sont traitées, et où ? »**
CV et réponses : PostgreSQL local. Traitement IA : local. Le seul envoi externe est
l'email d'invitation (adresse + poste + lien + PIN). Rien d'autre ne quitte la machine.

**« Quelle est la contribution originale ? »**
Le **Reality Gap Score** : croiser automatiquement le *déclaré* (CV parsé par le
pipeline NLP) et le *démontré* (test IRT + notation sémantique) pour produire un indice
de **cohérence du CV** — avec un radar par compétence et un score de matching ajusté.

## 3.4 Limites (honnêteté scientifique)

1. **Qualité du modèle local** : Mistral 7B produit occasionnellement une question
   discutable malgré les filtres (~1/16 observé). Mitigé par la vérification humaine
   possible et l'upgrade facile du modèle (`OLLAMA_MODEL`).
2. **Première génération lente** (~5-8 min par offre) — mitigée par l'arrière-plan et
   le cache par offre.
3. **Niveau déclaré dérivé** : les CV n'indiquent presque jamais un niveau chiffré
   (1 % des cas mesurés) ; la formule de dérivation est transparente mais reste une
   heuristique.
4. **Anti-triche web** : un second appareil ou une tierce personne restent indétectables
   par un navigateur — d'où l'importance du score d'intégrité et de l'entretien final
   humain pour contre-vérifier.

---

*Document généré le 11/07/2026 — branche `feature/reality-gap-score`.*
