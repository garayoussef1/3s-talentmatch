# Guide Rapide : De Slides Markdown à PowerPoint

## Étape 1 : Créer Présentation PowerPoint

### Option A : À partir de Google Slides (recommandé)
1. Aller sur https://docs.google.com/presentation/
2. Créer nouvelle présentation
3. Copier titre et contenu de chaque slide depuis `SLIDES_PRESENTATION.md`
4. Appliquer thème 3S (bleu/blanc/gris)

### Option B : PowerPoint Desktop
1. Ouvrir PowerPoint
2. Créer 15 slides
3. Copier contenu slide par slide
4. Ajouter images/logos 3S

---

## Étape 2 : Design Recommandé

### Palette Couleurs 3S
- **Primaire** : Bleu professionnel (#1F4788 ou équivalent)
- **Secondaire** : Gris clair (#E0E0E0)
- **Accent** : Vert (pour ✅ et points positifs)
- **Texte** : Noir (#222222) ou Blanc (sur fond bleu)

### Structure Chaque Slide
- **En-tête** : Numéro + Titre (police 40pt, bold)
- **Corps** : Points clés (police 24pt)
- **Pied** : Logo 3S + Numéro slide

### Polices Suggerées
- **Titres** : Arial, Segoe UI, ou Helvetica (sans-serif)
- **Corps** : Calibri ou Open Sans (lisible à distance)
- **Monospace** (code) : Consolas ou Courier New

---

## Étape 3 : Fichiers à Fournir

### Documents à Créer
1. ✅ `Presentation_3S_TalentMatch.pptx` (slides)
2. ✅ `Handout_Slides.pdf` (impression 6 slides/page)
3. ✅ `Notes_Presentation.docx` (notes personnelles pour chaque slide)
4. ✅ `Demo_Video.mp4` (backup vidéo 5 min)

### Documents Existants à Référencer
- `CONCEPT_PRESENTATION_1ER_RESTITUTION.md` (concept détaillé)
- `SLIDES_PRESENTATION.md` (ce fichier)
- `bilan_v1.tex` (rapport technique)
- `matching.md` (doc IA technique)

---

## Étape 4 : Préparation Démo

### Avant Présentation
```bash
# Terminal 1 : Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 : Frontend
cd frontend
npm install
npm run dev
```

### CVs et Offres de Démo
Préparer et sauvegarder dans un dossier `demo/`:
- ✅ `cv_demo_1.pdf` (un CV réel ou test)
- ✅ `offre_demo_backend.json` (offre Backend Python)

### Raccourcis Clavier à Noter
- Alt+Tab : bascule terminal/navigateur
- F5 : rafraîchir navigateur
- F12 : DevTools (si besoin montrer API calls)

---

## Étape 5 : Backup Plan

### Si démo en direct échoue
1. Lancer vidéo enregistrée (1-2 min)
2. Montrer screenshots des interfaces
3. Afficher JSON responses de l'API (curl ou Postman)
4. Passer directement aux questions

### Vidéo Démo à Enregistrer
```bash
# OBS ou ScreenFlow
# Enregistrer :
# 1. Upload CV (5 sec)
# 2. Créer offre (10 sec)
# 3. Matcher et voir score (15 sec)
# 4. Ouvrir rapport modal (10 sec)
# Total : ~40-50 sec
```

---

## Étape 6 : Réponses Anticipées aux Questions

### Q : "Comment fonctionne le matching BERT ?"
**R :** BERT convertit offre et CV en vecteurs numériques (embeddings), puis compare leur similarité avec cosine similarity. Ça comprend le sens : "Python developer" ≈ "Dev Python" même avec des mots différents. On ajoute aussi la détection d'incohérences : si candidat déclare "TensorFlow" mais aucune mention concrète dans CV, on le pénalise.

### Q : "Pourquoi 3 moteurs de matching ?"
**R :** 
- Heuristique = fiable en prod, expliquable, rapide
- ML = expérimentation (dataset limité pour le moment)
- BERT = avenir, sémantique profonde, multilingue
On les compare pour montrer qu'IA aide mais pas remplace.

### Q : "Combien de temps de calcul matching ?"
**R :** Heuristique : <500ms. BERT : 1-3 sec sur CPU. Acceptable pour un POC, optimisable avec GPU ou cache.

### Q : "RGPD, comment c'est géré ?"
**R :** Consentement explicite avant upload. Logs audit de qui accède à quoi. Anonymisation automatique possible. Droit à l'oubli = suppression complète de la base. Pas de vente données.

### Q : "Multilingue comment ?"
**R :** Modèle BERT `paraphrase-multilingual-MiniLM-L12-v2` : 50+ langues natives sans traduction. FR et EN spécifiquement optimisés.

### Q : "Déploiement ?"
**R :** Actuellement local. Roadmap : Docker + AWS/Heroku. API stateless, facile à scaler horizontalement.

---

## Étape 7 : Livrables Finaux (Checklist)

### 📋 À Fournir Avant Restitution

- [ ] **Slides PowerPoint** (15 slides formatées)
- [ ] **Handout PDF** (imprimable)
- [ ] **Notes Présentation** (document Word/Google Docs)
- [ ] **Vidéo Démo** (40-50 sec, backup)
- [ ] **Rapport Technique** (bilan_v1.tex)
- [ ] **Doc Matching IA** (matching.md)
- [ ] **Code Source** (GitHub ou archive)
- [ ] **Démo Live Testée** (backend + frontend ok)

### 📧 Email Avant Présentation

Subject : Matériels 1ère Restitution - 3S TalentMatch

Corps :
```
Bonjour [Expert],

Ci-joint les matériels pour la 1ère restitution :
- Slides présentation (15 slides, 15 min)
- Rapport technique détaillé
- Code source complet
- Vidéo démo (backup)

Démo en direct prévue sur machine locale.

Besoin de projecteur + accès internet.

Cordialement,
Youssef
```

---

## Étape 8 : Jour de la Restitution

### Morning-of Checklist
- [ ] Dormir bien
- [ ] Vérifier tenue professionnelle
- [ ] Charger laptop (100%)
- [ ] Tester démo 30 min avant
- [ ] Apporter adaptateur HDMI/USB
- [ ] Imprimer handouts (10 copies)
- [ ] Relire notes dernière fois

### Avant de Commencer
- ✅ Dire bonjour jury + expert
- ✅ Tester micro/vidéo/écran partagé
- ✅ Afficher slide 1
- ✅ Respirer profondément

### Pendant Présentation
- 📌 Parler clair, pas trop vite
- 📌 Regard jury (pas sur écran)
- 📌 Gestes naturels
- 📌 Si vous oubliez quelque chose = continuer (pas revenir en arrière)
- 📌 Notes sur papier autorisées (mais pas texte complet)

### Questions à la Fin
- ✅ Écouter complètement
- ✅ Reformuler si pas clair
- ✅ Répondre honnêtement ("je ne sais pas" = acceptable)
- ✅ Rester calme

---

## Ressources Utiles

### Créer Slides Rapidement
- **Google Slides Template** : slides.google.com
- **PowerPoint Template** : office.microsoft.com
- **Canva Pro** : canva.com (templates RH/tech)

### Vidéo Démo
- **OBS Studio** (gratuit) : obsproject.com
- **ScreenFlow** (Mac) : telestream.net
- **Camtasia** (payant) : camtasia.com

### Pour Exporter
- Google Slides → Télécharger en .pptx
- PowerPoint → Fichier → Exporter en PDF

---

**Prêt pour la restitution ? 🚀**

Questions sur les slides ou la démo ?
