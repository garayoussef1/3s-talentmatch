# 3S TalentMatch — Frontend

Interface utilisateur React pour la plateforme de matching CV/offres d'emploi.

## Stack technique

- **React 18** — bibliothèque UI
- **Vite 5** — bundler ultra-rapide
- **React Router DOM 6** — navigation SPA
- **Axios** — client HTTP
- **Tailwind CSS** — utility-first CSS

---

## Prérequis

- Node.js **v18+** (recommandé : v22)
- npm 9+
- Backend FastAPI démarré sur le port **8000**

---

## Installation

### 1. Se placer dans le dossier frontend

```bash
cd frontend
```

### 2. Installer les dépendances

```bash
npm install
```

---

## Démarrer en développement

```bash
npm run dev
```

L'application est accessible sur : http://localhost:3000

> Le proxy Vite redirige automatiquement `/api/*` → `http://localhost:8000`

---

## Build de production

```bash
npm run build
```

Les fichiers optimisés sont générés dans `frontend/dist/`.

### Prévisualiser le build

```bash
npm run preview
```

---

## Pages disponibles

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Dashboard avec statistiques |
| `/upload` | UploadCV | Upload drag & drop d'un CV |
| `/candidates` | Candidates | Liste des candidats en BDD |

---

## Structure du projet

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── Navbar.jsx        # Barre de navigation
│   │   └── Navbar.css
│   ├── pages/
│   │   ├── Home.jsx          # Dashboard
│   │   ├── Home.css
│   │   ├── UploadCV.jsx      # Upload drag & drop
│   │   ├── UploadCV.css
│   │   ├── Candidates.jsx    # Liste candidats
│   │   └── Candidates.css
│   ├── App.jsx               # Routes principale
│   ├── App.css
│   ├── main.jsx              # Point d'entrée React
│   └── index.css             # Styles globaux + Tailwind
├── index.html
├── vite.config.js            # Config Vite (port 3000 + proxy)
├── tailwind.config.js        # Config Tailwind CSS
├── postcss.config.js
└── package.json
```

---

## Variables d'environnement

Par défaut, le proxy Vite pointe vers `http://localhost:8000`.  
Pour changer l'URL du backend, modifier `vite.config.js` :

```js
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    ...
  }
}
```

### OAuth (Google / LinkedIn)

Le bouton "Continuer avec Google" utilise un `client_id` **public** côté frontend.

- Créer `frontend/.env` (ou `frontend/.env.local`) à partir de `frontend/.env.example`
- Renseigner :
  - `VITE_GOOGLE_CLIENT_ID`
  - `VITE_LINKEDIN_CLIENT_ID` (optionnel)
- Redémarrer `npm run dev`

Redirect URIs à déclarer côté providers (dev) :
- Google: `http://localhost:3000/auth/callback/google`
- LinkedIn: `http://localhost:3000/auth/callback/linkedin`

---

## Dépendances principales

| Package | Version | Rôle |
|---------|---------|------|
| react | ^18.3.1 | Bibliothèque UI |
| react-dom | ^18.3.1 | Rendu DOM |
| react-router-dom | ^6.22.3 | Routing SPA |
| axios | ^1.6.8 | Requêtes HTTP |
| vite | ^5.2.0 | Build tool |
| @vitejs/plugin-react | ^4.3.1 | Support JSX |
| tailwindcss | ^3.x | CSS utilities |
