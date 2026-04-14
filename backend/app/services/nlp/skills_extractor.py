"""
Extraction de compétences techniques depuis un texte de CV.
Sprint 2 - US-207

Fonctionnalités :
- Base de 300+ compétences classées par catégorie
- Matching case-insensitive avec gestion synonymes
- Isolation section Compétences (poids élevé) + texte entier (poids faible)
- Protection faux positifs : skills 1-2 lettres (C, R) avec contexte requis
- Extraction années d'expérience par compétence
- Inférence du niveau automatique (Débutant → Expert)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    from rapidfuzz import process as _fuzz_process, fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    _RAPIDFUZZ_AVAILABLE = False

logger = logging.getLogger(__name__)


# ================================================================
# Base de compétences 300+ items, classées par catégorie
# ================================================================

SKILLS_DATABASE: Dict[str, List[str]] = {
    "langages": [
        "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#",
        "PHP", "Ruby", "Go", "Golang", "Rust", "Swift", "Kotlin",
        "Scala", "Perl", "R", "Matlab", "Lua", "Dart", "Haskell",
        "Objective-C", "Shell", "Bash", "PowerShell", "SQL", "PL/SQL",
        "Assembly", "VHDL", "Verilog", "Groovy", "Elixir", "Clojure",
        "F#", "Julia", "Fortran", "COBOL", "VBA", "Delphi",
        "HTML", "HTML5", "CSS", "CSS3", "SASS", "SCSS", "LESS",
        "Zig", "Nim", "Crystal", "V", "Carbon",
    ],
    "frameworks_web": [
        "React", "Angular", "Vue.js", "Vue", "Svelte", "Next.js",
        "Nuxt.js", "Gatsby", "Remix", "Astro", "SvelteKit",
        "Django", "Flask", "FastAPI", "Express", "Express.js",
        "NestJS", "Spring", "Spring Boot", "Laravel", "Symfony",
        "Ruby on Rails", "Rails", "ASP.NET", ".NET", ".NET Core",
        "Gin", "Fiber", "Echo", "Actix", "Rocket",
        "Struts", "Play Framework", "Quarkus", "Micronaut",
        "Node.js", "Qt", "Bootstrap", "Tailwind CSS",
        "Hono", "Elysia", "tRPC", "Prisma", "Drizzle ORM",
        "Zod", "React Query", "TanStack Query", "SWR",
        "Redux", "Zustand", "Pinia", "MobX", "Recoil",
        "Nx", "Turborepo", "Lerna",
    ],
    "frameworks_mobile": [
        "React Native", "Flutter", "FlutterFlow", "SwiftUI", "Jetpack Compose",
        "Xamarin", "Ionic", "Cordova", "Capacitor", "Kivy",
        "NativeScript", "Expo", "Tauri",
    ],
    "bases_de_donnees": [
        "PostgreSQL", "Postgres", "MySQL", "MariaDB", "Oracle",
        "SQL Server", "SQLite", "MongoDB", "Redis", "Cassandra",
        "DynamoDB", "CouchDB", "Neo4j", "InfluxDB", "Elasticsearch",
        "Firebase", "Firestore", "Supabase", "Memcached",
        "TimescaleDB", "CockroachDB", "ClickHouse",
        "PlanetScale", "Neon", "Turso", "LibSQL",
        "Pinecone", "Weaviate", "Qdrant", "ChromaDB",
    ],
    "devops_cloud": [
        "Docker", "Kubernetes", "K8s", "Terraform", "Ansible",
        "Jenkins", "GitLab CI", "GitHub Actions", "CircleCI",
        "Travis CI", "ArgoCD", "Helm", "Vagrant", "Packer",
        "AWS", "Amazon Web Services", "Azure", "Google Cloud", "GCP",
        "Heroku", "DigitalOcean", "Vercel", "Netlify", "Cloudflare",
        "OpenStack", "Proxmox", "VMware",
        "Prometheus", "Grafana", "Datadog", "New Relic", "ELK",
        "Logstash", "Kibana", "Nagios", "Zabbix",
        "Pulumi", "Coolify", "Railway", "Render", "Fly.io",
        "Podman", "containerd", "Istio", "Linkerd",
        "AWS Lambda", "Azure Functions", "Google Cloud Functions",
        "Serverless Framework",
    ],
    "outils_dev": [
        "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
        "VS Code", "IntelliJ", "Eclipse", "PyCharm", "WebStorm",
        "Jira", "Confluence", "Trello", "Notion", "Asana",
        "Postman", "Insomnia", "Swagger", "OpenAPI",
        "Webpack", "Vite", "Babel", "ESLint", "Prettier",
        "npm", "yarn", "pnpm", "pip", "Maven", "Gradle",
        "CMake", "Make", "Bazel",
        "Figma", "Linear", "Cursor", "GitHub Copilot",
        "Storybook", "Chromatic", "Vitest", "Bun", "Deno",
        "Bruno", "HTTPie",
    ],
    "data_ml_ia": [
        "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch",
        "Keras", "XGBoost", "LightGBM", "CatBoost", "NLTK",
        "spaCy", "Hugging Face", "Transformers", "OpenCV",
        "Matplotlib", "Seaborn", "Plotly", "Tableau", "Power BI",
        "Apache Spark", "PySpark", "Hadoop", "Hive", "Airflow",
        "MLflow", "Kubeflow", "DVC", "Weights & Biases",
        "Jupyter", "Google Colab", "SageMaker", "Vertex AI",
        "LangChain", "GPT", "BERT", "CamemBERT",
        "RAG", "LLM", "Deep Learning", "Machine Learning",
        "NLP", "Computer Vision", "Reinforcement Learning",
        "SSIS", "ETL", "OLAP", "Data Warehouse",
        "Generative AI", "CLIP",
        "OpenAI API", "Gemini API", "Gemini", "Hugging Face",
        "API Platform", "Stripe",
        "LlamaIndex", "CrewAI", "AutoGen", "Ollama",
        "Mistral", "Llama", "Stable Diffusion",
        "DBT", "dbt", "Metabase", "Looker", "Superset",
        "Polars", "Dask", "Ray",
    ],
    "securite": [
        "OWASP", "Burp Suite", "Metasploit", "Nmap", "Wireshark",
        "Nessus", "Snort", "Suricata", "Kali Linux",
        "SSL/TLS", "OAuth", "OAuth2", "JWT", "SAML",
        "LDAP", "Active Directory", "Keycloak",
        "Cryptographie", "Pentesting", "Firewall",
    ],
    "systemes_reseaux": [
        "Linux", "Ubuntu", "Debian", "CentOS", "Red Hat", "RHEL", "Kali",
        "Windows Server", "macOS",
        "Nginx", "Apache", "Caddy", "HAProxy",
        "TCP/IP", "DNS", "DHCP", "HTTP", "HTTPS", "REST",
        "GraphQL", "gRPC", "WebSocket", "MQTT", "AMQP",
        "RabbitMQ", "Kafka", "Apache Kafka", "ZeroMQ", "Celery",
        "Cisco Packet Tracer", "GNS3", "Wireshark",
    ],
    "tests_qualite": [
        "Pytest", "JUnit", "Jest", "Mocha", "Chai", "Cypress",
        "Selenium", "Playwright", "Robot Framework",
        "unittest", "nose", "TestNG", "PHPUnit", "RSpec",
        "SonarQube", "SonarCloud", "Coveralls", "Codecov",
        "TDD", "BDD", "CI/CD",
    ],
    "methodologies": [
        "Agile", "Scrum", "Kanban", "SAFe", "XP",
        "DevOps", "DevSecOps", "SRE",
        "Microservices", "Monolithique", "Serverless",
        "Event-Driven", "CQRS", "DDD",
        "Design Patterns", "SOLID", "Clean Architecture",
        "UML", "Merise",
    ],
    "soft_skills": [
        "Gestion de projet", "Management", "Leadership",
        "Communication", "Travail en équipe", "Teamwork",
        "Résolution de problèmes", "Problem Solving",
        "Créativité", "Autonomie", "Adaptabilité",
        "Esprit critique", "Organisation", "Rigueur",
        "Négociation", "Présentation", "Rédaction technique",
        "Prospection", "Développement commercial", "Vente", "Relation client",
        "Gestion de portefeuille", "Gestion de portefeuille clients",
        "Appels d'offres", "Analyse des besoins",
        "Up-selling", "Cross-selling", "Upselling", "Cross selling", "Up selling",
        "B2B", "B2C", "Account Management",
    ],
    "marketing_digital": [
        "Google Ads", "Facebook Ads", "LinkedIn Ads", "Twitter Ads",
        "Instagram Ads", "TikTok Ads", "Snapchat Ads", "Pinterest Ads",
        "SEO", "SEM", "PPC", "CRO", "SEA", "SMO",
        "Google Analytics", "Google Analytics 4", "GA4",
        "Google Tag Manager", "GTM",
        "Google Search Console",
        "SEMrush", "Ahrefs", "Moz", "Screaming Frog", "Ubersuggest",
        "Mailchimp", "ActiveCampaign", "Sendinblue", "GetResponse",
        "HubSpot", "Salesforce Marketing Cloud", "Marketo", "Pardot",
        "Hootsuite", "Buffer", "Sprout Social", "Later", "Planoly",
        "Canva", "Adobe Photoshop", "Adobe Illustrator", "Adobe InDesign",
        "Figma", "Adobe XD", "Sketch",
        "WordPress", "Shopify", "WooCommerce", "Webflow", "Squarespace",
        "Email Marketing", "Content Marketing", "Inbound Marketing",
        "Growth Hacking", "A/B Testing", "Copywriting",
        "Social Media Marketing", "Influencer Marketing", "Affiliate Marketing",
        "Community Management", "Meta Ads", "Facebook Business Manager",
        "CRM", "Salesforce",
    ],
    "comptabilite_finance": [
        "Sage", "Ciel", "EBP", "Compta Pro", "Quadratus",
        "SAP", "SAP FI", "SAP CO", "SAP FI/CO", "SAP FICO",
        "Odoo", "Oracle", "Microsoft Dynamics", "NetSuite",
        "IFRS", "PCG", "Normes IFRS", "PCG tunisien", "Normes comptables",
        "Audit", "Audit financier", "Audit interne", "Audit externe",
        "Commissariat aux comptes", "Révision comptable",
        "Consolidation", "Consolidation comptes", "Liasses fiscales",
        "Comptabilité générale", "Comptabilité analytique",
        "Gestion budgétaire", "Contrôle de gestion",
        "Analyse financière", "Reporting financier", "Business plan",
        "Fiscalité", "Déclarations fiscales", "Optimisation fiscale",
        "IS", "TVA", "IR", "Taxe professionnelle", "Droits d'enregistrement",
        "Trésorerie", "Cash flow", "BFR", "Fonds de roulement",
    ],
    "sante_medical": [
        "Soins intensifs", "Soins d'urgence", "Soins critiques",
        "Réanimation", "RCP", "Réanimation cardio-pulmonaire",
        "Monitoring cardiaque", "ECG", "Électrocardiogramme",
        "Ventilation mécanique", "Intubation",
        "Cathétérisme", "Perfusions", "Perfusions IV", "Voie veineuse",
        "Prélèvements sanguins", "Ponction veineuse",
        "Pansements", "Soins post-opératoires", "Soins de plaies",
        "Gestion douleur", "Analgésie", "Soins palliatifs",
        "Asepsie", "Hygiène hospitalière", "Protocoles d'hygiène",
        "Éducation thérapeutique", "Éducation patient",
        "Gestion équipement médical", "Pompe à perfusion",
        "Hosix", "Dossier patient électronique", "DMI",
        "Protocoles de soins", "Normes HACCP",
    ],
    "rh_recrutement": [
        "Workday", "SAP SuccessFactors", "SAP HCM",
        "Lever", "Greenhouse", "Recruitee", "Taleo", "SmartRecruiters",
        "LinkedIn Recruiter", "Indeed", "Welcome to the Jungle",
        "BambooHR", "Gusto", "Personio", "Zenefits",
        "GPEC", "Gestion prévisionnelle emplois", "GEPP",
        "ATS", "Applicant Tracking System", "SIRH",
        "Recrutement", "Sourcing", "Talent Acquisition", "Chasse de têtes",
        "Assessment", "Assessment center", "Tests psychométriques",
        "Onboarding", "Parcours d'intégration",
        "Gestion paie", "Paie", "Charges sociales",
        "Relations sociales", "Droit du travail", "Négociation syndicale",
        "Plan de formation", "CPF", "OPCO",
        "Entretien annuel", "Entretien professionnel",
    ],
    "metiers_manuels": [
        "Installation électrique", "Électricité bâtiment", "Électricité industrielle",
        "Tableaux électriques", "Câblage électrique", "Schémas électriques",
        "Normes électriques", "Norme NFC 15-100", "Normes CE",
        "Habilitation électrique", "Habilitation B1V", "Habilitation B2V",
        "Habilitation BR", "Habilitation BC",
        "Dépannage électrique", "Maintenance électrique",
        "Plomberie", "Sanitaire", "Chauffage", "Climatisation",
        "Menuiserie", "Charpente", "Ébénisterie",
        "Maçonnerie", "Gros œuvre", "Béton armé",
        "Peinture", "Revêtements", "Carrelage",
        "Soudure", "Soudure TIG", "Soudure MIG",
        "Mécanique auto", "Mécanique industrielle", "Maintenance mécanique",
        "Lecture de plans", "Plans techniques",
    ],

    # ── DROIT & JURIDIQUE ──────────────────────────────────────────────────────
    "droit_juridique": [
        # Branches du droit
        "Droit civil", "Droit commercial", "Droit des affaires", "Droit pénal",
        "Droit du travail", "Droit administratif", "Droit fiscal",
        "Droit international", "Droit européen", "Droit de la famille",
        "Droit des sociétés", "Droit immobilier", "Droit bancaire",
        "Droit de la propriété intellectuelle", "Droit des contrats",
        "Droit public", "Droit privé", "Droit constitutionnel",
        "Droit de la concurrence", "Droit des assurances",
        # Compétences juridiques
        "Rédaction d'actes", "Rédaction juridique", "Actes notariés",
        "Contentieux", "Gestion du contentieux", "Procédure civile",
        "Procédure pénale", "Procédure administrative",
        "Conseil juridique", "Veille juridique", "Veille réglementaire",
        "Due diligence", "Négociation contractuelle",
        "Contrats commerciaux", "Contrats de travail",
        "Statuts de société", "Assemblées générales",
        "Fusion-acquisition", "M&A",
        # Outils / cadre
        "LexisNexis", "Dalloz", "Juris Data", "Lamyline",
        "Codes juridiques", "Jurisprudence",
        "RGPD", "Conformité", "Compliance",
        "ISO 9001", "ISO 27001",
    ],

    # ── ARCHITECTURE & BTP ────────────────────────────────────────────────────
    "architecture_btp": [
        # Logiciels CAO/DAO
        "AutoCAD", "AutoCAD 2D", "AutoCAD 3D",
        "Revit", "Revit Architecture", "Revit Structure", "Revit MEP",
        "ArchiCAD", "SketchUp", "Rhino", "Rhinoceros",
        "3ds Max", "Blender", "Lumion", "Enscape", "V-Ray",
        "Vectorworks", "Civil 3D", "Tekla Structures",
        "BIM", "BIM 360", "Navisworks", "BIM Collaborate",
        "Adobe Photoshop", "Adobe Illustrator", "InDesign",
        # Documents techniques
        "Plans d'architecture", "Plans d'exécution", "Dessins techniques",
        "CCTP", "DPGF", "DCE", "CCAP", "Cahier des charges techniques",
        "Permis de construire", "Déclaration préalable",
        "Plans de masse", "Plans de coupe", "Façades",
        "Métrés", "Estimatif", "Devis quantitatif",
        # Suivi chantier / maîtrise d'œuvre
        "Suivi de chantier", "Conduite de travaux", "Maîtrise d'œuvre",
        "Maîtrise d'ouvrage", "Coordination de chantier",
        "Réception de travaux", "Levée de réserves",
        "Planification", "Planning travaux", "MS Project",
        "Gestion budgétaire chantier", "Contrôle des coûts",
        # Normes & réglementation
        "Réglementation thermique", "RT 2012", "RE 2020",
        "Normes parasismiques", "Eurocode",
        "Accessibilité PMR", "Sécurité incendie",
        "Urbanisme", "PLU", "Plan local d'urbanisme",
        # Structures & matériaux
        "Béton armé", "Charpente métallique", "Structure bois",
        "Géotechnique", "Hydraulique", "Topographie",
        "Calcul de structures", "RDM", "Résistance des matériaux",
    ],

    # ── SCIENCES PURES & RECHERCHE ────────────────────────────────────────────
    "sciences_recherche": [
        # Biologie / Biochimie
        "Biologie moléculaire", "Biochimie", "Microbiologie", "Génétique",
        "Biologie cellulaire", "Immunologie", "Virologie",
        "PCR", "PCR quantitative", "qPCR", "Électrophorèse",
        "Chromatographie", "HPLC", "Spectrophotométrie",
        "Culture cellulaire", "Western blot", "ELISA",
        "Séquençage", "NGS", "Bioinformatique",
        # Chimie
        "Chimie analytique", "Chimie organique", "Chimie inorganique",
        "Chimie des matériaux", "Spectroscopie", "RMN", "Spectrométrie de masse",
        "Chromatographie en phase gazeuse", "GC-MS",
        "Titration", "Synthèse chimique",
        # Physique
        "Mécanique quantique", "Optique", "Électromagnétisme",
        "Thermodynamique", "Électronique",
        "Mesures physiques", "Instrumentation scientifique",
        # Méthodes de recherche
        "Recherche scientifique", "Rédaction scientifique",
        "Publications scientifiques", "Revue de littérature",
        "Protocoles expérimentaux", "Plan d'expérience", "DOE",
        "Analyse statistique", "SPSS", "R", "SAS", "Minitab",
        "Laboratoire", "BPL", "Bonnes Pratiques de Laboratoire",
        # Environnement
        "Environnement", "Écologie", "Évaluation d'impact environnemental",
        "ISO 14001", "Développement durable",
    ],

    # ── ENSEIGNEMENT & PÉDAGOGIE ──────────────────────────────────────────────
    "enseignement_pedagogie": [
        # Méthodes pédagogiques
        "Pédagogie", "Didactique", "Ingénierie pédagogique",
        "Conception de cours", "Élaboration de programmes",
        "Évaluation des apprentissages", "Évaluation formative",
        "Pédagogie différenciée", "Apprentissage par projet",
        "Pédagogie active", "Classe inversée", "Blended learning",
        "E-learning", "Formation à distance", "FOAD",
        # Outils
        "Moodle", "Google Classroom", "Teams for Education",
        "Zoom", "Padlet", "Kahoot", "Mentimeter",
        "Tableau interactif", "TBI",
        # Niveaux
        "Enseignement primaire", "Enseignement secondaire",
        "Enseignement supérieur", "Formation professionnelle",
        "Formation continue", "Tutorat", "Coaching",
        # Compétences
        "Gestion de classe", "Animation de groupe",
        "Accompagnement pédagogique", "Suivi individualisé",
        "Conception de supports de formation",
        "Évaluation et certification",
    ],

    # ── LOGISTIQUE & SUPPLY CHAIN ─────────────────────────────────────────────
    "logistique_supply_chain": [
        # ERP & WMS
        "SAP MM", "SAP SD", "SAP WM", "SAP EWM",
        "SAP S/4HANA", "Oracle SCM", "JDA", "Manhattan Associates",
        "WMS", "TMS", "ERP", "ERP logistique",
        "Sage 100 Gestion Commerciale", "Odoo Inventory",
        # Gestion des stocks
        "Gestion des stocks", "Gestion des entrepôts",
        "Inventaire", "FIFO", "LIFO", "Gestion FIFO",
        "Approvisionnement", "Gestion des approvisionnements",
        "MRP", "MRP2", "Planification de la production",
        "Kanban", "Just-in-time", "Lean Manufacturing", "Lean",
        "5S", "Kaizen", "Six Sigma",
        # Transport & Distribution
        "Transport", "Gestion du transport",
        "Incoterms", "Commerce international", "Import-export",
        "Dédouanement", "Douane", "Transit douanier",
        "Logistique internationale", "Fret aérien", "Fret maritime",
        "Gestion des transporteurs", "Optimisation des tournées",
        # Achats
        "Achats", "Gestion des achats", "Négociation fournisseurs",
        "Appels d'offres", "Sourcing", "Gestion des fournisseurs",
        "Contrats d'achat",
    ],

    # ── AGROALIMENTAIRE & QUALITÉ ─────────────────────────────────────────────
    "agroalimentaire_qualite": [
        # Sécurité alimentaire
        "HACCP", "Plan HACCP", "Analyse des dangers",
        "ISO 22000", "IFS", "BRC", "FSSC 22000",
        "Bonnes Pratiques d'Hygiène", "BPH",
        "Bonnes Pratiques de Fabrication", "BPF",
        "Traçabilité", "Traçabilité alimentaire",
        "Contrôle qualité alimentaire", "Contrôle qualité",
        "Microbiologie alimentaire", "Analyses microbiologiques",
        # Procédés
        "Technologie alimentaire", "Procédés agroalimentaires",
        "Formulation", "Développement produit",
        "Analyse sensorielle", "Dégustation",
        "Conditionnement", "Emballage alimentaire",
        # Qualité générale
        "Management de la qualité", "SMQ", "Système de management",
        "ISO 9001", "Audit qualité", "Non-conformités",
        "Actions correctives", "AMDEC",
        "Contrôle statistique", "SPC", "MSP",
        "Métrologie", "Étalonnage",
        # Réglementation
        "Réglementation alimentaire", "Étiquetage",
        "Droit alimentaire", "Règlement CE", "FDA",
    ],
}

# ================================================================
# Synonymes : alias → nom canonique
# ================================================================

SYNONYMS: Dict[str, str] = {
    # Langages
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "c sharp": "C#",
    "csharp": "C#",
    "cplusplus": "C++",
    "objective c": "Objective-C",
    "golang": "Go",
    # Frameworks
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "angularjs": "Angular",
    "angular.js": "Angular",
    "vuejs": "Vue.js",
    "vue js": "Vue.js",
    "nextjs": "Next.js",
    "nuxtjs": "Nuxt.js",
    "expressjs": "Express.js",
    "express js": "Express.js",
    "nestjs": "NestJS",
    "springboot": "Spring Boot",
    "spring-boot": "Spring Boot",
    "rubyonrails": "Ruby on Rails",
    "ror": "Ruby on Rails",
    "asp.net": "ASP.NET",
    "dotnet": ".NET",
    "dot net": ".NET",
    ".net core": ".NET Core",
    "fast api": "FastAPI",
    "tailwindcss": "Tailwind CSS",
    "nodejs": "Node.js",
    "node js": "Node.js",
    # BDD
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongo db": "MongoDB",
    "sql server": "SQL Server",
    "mssql": "SQL Server",
    "maria db": "MariaDB",
    "mariadb": "MariaDB",
    "elastic search": "Elasticsearch",
    "elastic": "Elasticsearch",
    # DevOps
    "k8s": "Kubernetes",
    "kube": "Kubernetes",
    "docker compose": "Docker",
    "docker-compose": "Docker",
    "github action": "GitHub Actions",
    "github-actions": "GitHub Actions",
    "gitlab ci": "GitLab CI",
    "gitlab-ci": "GitLab CI",
    "circle ci": "CircleCI",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    # Data / IA
    "sklearn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "hf": "Hugging Face",
    "huggingface": "Hugging Face",
    "hugging face": "Hugging Face",
    "opencv": "OpenCV",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "deep learning": "Deep Learning",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "ia": "Machine Learning",
    "ai": "Machine Learning",
    "llm": "LLM",
    "langchain": "LangChain",
    # Outils
    "vscode": "VS Code",
    "visual studio code": "VS Code",
    "intellij idea": "IntelliJ",
    # Node.js / runtime
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "bun.js": "Bun",
    "bunjs": "Bun",
    "deno.js": "Deno",
    # ORM / query
    "prisma orm": "Prisma",
    "drizzle": "Drizzle ORM",
    "drizzle orm": "Drizzle ORM",
    "react query": "React Query",
    "tanstack query": "TanStack Query",
    "tanstack": "TanStack Query",
    # State management
    "zustand": "Zustand",
    "pinia": "Pinia",
    "recoil": "Recoil",
    "mobx": "MobX",
    # Mobile
    "flutterflow": "FlutterFlow",
    "flutter flow": "FlutterFlow",
    "expo": "Expo",
    # DevOps nouveaux
    "fly.io": "Fly.io",
    "railway": "Railway",
    "render": "Render",
    "coolify": "Coolify",
    "pulumi": "Pulumi",
    "serverless": "Serverless Framework",
    # DB vectorielles
    "pinecone": "Pinecone",
    "weaviate": "Weaviate",
    "qdrant": "Qdrant",
    "chromadb": "ChromaDB",
    # IA / LLM nouveaux
    "llamaindex": "LlamaIndex",
    "llama index": "LlamaIndex",
    "crewai": "CrewAI",
    "crew ai": "CrewAI",
    "autogen": "AutoGen",
    "auto gen": "AutoGen",
    "ollama": "Ollama",
    "mistral": "Mistral",
    "stable diffusion": "Stable Diffusion",
    "stablediffusion": "Stable Diffusion",
    # Data
    "dbt": "dbt",
    "metabase": "Metabase",
    "looker": "Looker",
    "superset": "Superset",
    "polars": "Polars",
    "dask": "Dask",
    "ray": "Ray",
    # Outils dev nouveaux
    "copilot": "GitHub Copilot",
    "github copilot": "GitHub Copilot",
    "cursor": "Cursor",
    "linear": "Linear",
    "storybook": "Storybook",
    "vitest": "Vitest",
    # Data
    "etl": "ETL",
    "ssis": "SSIS",
    "data warehouse": "Data Warehouse",
    "olap": "OLAP",
    # Réseau
    "cisco packet tracer": "Cisco Packet Tracer",
    "packet tracer": "Cisco Packet Tracer",
    # AI
    "generative ai": "Generative AI",
    "generative models": "Generative AI",
    "clip": "CLIP",
    # Tests
    "ci/cd": "CI/CD",
    "ci cd": "CI/CD",
    "tdd": "TDD",
    "bdd": "BDD",
    # Méthodo
    "design pattern": "Design Patterns",
    "design patterns": "Design Patterns",
    "clean archi": "Clean Architecture",
    "micro services": "Microservices",
    "micro-services": "Microservices",
    # Marketing
    "google ads": "Google Ads",
    "facebook ads": "Facebook Ads",
    "linkedin ads": "LinkedIn Ads",
    "ga4": "Google Analytics 4",
    "gtm": "Google Tag Manager",
    "semrush": "SEMrush",
    "hubspot": "HubSpot",
    "a/b testing": "A/B Testing",
    "ab testing": "A/B Testing",
    "social media": "Social Media Marketing",
    "crm": "CRM",
    "up selling": "Up-selling",
    "upselling": "Up-selling",
    "cross selling": "Cross-selling",
    "cross-selling": "Cross-selling",
    "appel d'offre": "Appels d'offres",
    "appels d'offre": "Appels d'offres",
    "b2b": "B2B",
    "b2c": "B2C",
    # Comptabilité
    "sap fi": "SAP FI",
    "sap co": "SAP CO",
    "sap fi/co": "SAP FI/CO",
    "compta": "Comptabilité générale",
    "comptabilite generale": "Comptabilité générale",
    "comptabilite analytique": "Comptabilité analytique",
    "controle de gestion": "Contrôle de gestion",
    "analyse financiere": "Analyse financière",
    "normes ifrs": "IFRS",
    # Santé
    "rcp": "RCP",
    "ecg": "ECG",
    "soins intensifs": "Soins intensifs",
    "reanimation": "Réanimation",
    # RH
    "gpec": "GPEC",
    "ats": "ATS",
    "talent acquisition": "Talent Acquisition",
    "gestion paie": "Gestion paie",
    "droit du travail": "Droit du travail",
    # Métiers manuels
    "installation electrique": "Installation électrique",
    "electricite batiment": "Électricité bâtiment",
    "cablage electrique": "Câblage électrique",
    "depannage electrique": "Dépannage électrique",
    "tableaux electriques": "Tableaux électriques",
    "mecanique auto": "Mécanique auto",
    # Synonymes enrichis - Comptabilité
    "sap fico": "SAP FICO",
    "netsuite": "NetSuite",
    "quadratus": "Quadratus",
    "audit interne": "Audit interne",
    "audit externe": "Audit externe",
    "revision comptable": "Révision comptable",
    "liasses fiscales": "Liasses fiscales",
    "business plan": "Business plan",
    "tresorerie": "Trésorerie",
    "cash flow": "Cash flow",
    "bfr": "BFR",
    "fonds de roulement": "Fonds de roulement",
    "optimisation fiscale": "Optimisation fiscale",
    # Synonymes enrichis - Santé
    "soins critiques": "Soins critiques",
    "intubation": "Intubation",
    "analgesie": "Analgésie",
    "education therapeutique": "Éducation thérapeutique",
    "education patient": "Éducation patient",
    "dmi": "DMI",
    "protocoles de soins": "Protocoles de soins",
    "normes haccp": "Normes HACCP",
    "hygiene hospitaliere": "Hygiène hospitalière",
    "pompe a perfusion": "Pompe à perfusion",
    # Synonymes enrichis - RH
    "sirh": "SIRH",
    "gepp": "GEPP",
    "chasse de tetes": "Chasse de têtes",
    "assessment center": "Assessment center",
    "tests psychometriques": "Tests psychométriques",
    "onboarding": "Onboarding",
    "charges sociales": "Charges sociales",
    "negociation syndicale": "Négociation syndicale",
    "plan de formation": "Plan de formation",
    "cpf": "CPF",
    "opco": "OPCO",
    "entretien annuel": "Entretien annuel",
    "entretien professionnel": "Entretien professionnel",
    # Synonymes enrichis - Métiers manuels
    "schemas electriques": "Schémas électriques",
    "maintenance electrique": "Maintenance électrique",
    "soudure tig": "Soudure TIG",
    "soudure mig": "Soudure MIG",
    "maintenance mecanique": "Maintenance mécanique",
    "lecture de plans": "Lecture de plans",
    "beton arme": "Béton armé",
    "ebenisterie": "Ébénisterie",
    # Synonymes enrichis - Marketing
    "pinterest ads": "Pinterest Ads",
    "meta ads": "Meta Ads",
    "community management": "Community Management",
    "affiliate marketing": "Affiliate Marketing",
    "facebook business manager": "Facebook Business Manager",
    "getresponse": "GetResponse",
    "pardot": "Pardot",
    "squarespace": "Squarespace",
    "adobe indesign": "Adobe InDesign",
    "sketch": "Sketch",
    # Droit
    "rgpd": "RGPD",
    "m&a": "M&A",
    "due diligence": "Due diligence",
    "lexisnexis": "LexisNexis",
    "droit des affaires": "Droit des affaires",
    "droit des societes": "Droit des sociétés",
    "droit immobilier": "Droit immobilier",
    "propriete intellectuelle": "Droit de la propriété intellectuelle",
    "compliance": "Conformité",
    "iso 27001": "ISO 27001",
    # Architecture / BTP
    "autocad": "AutoCAD",
    "archicad": "ArchiCAD",
    "sketchup": "SketchUp",
    "3ds max": "3ds Max",
    "bim 360": "BIM 360",
    "navisworks": "Navisworks",
    "cctp": "CCTP",
    "dpgf": "DPGF",
    "dce": "DCE",
    "re 2020": "RE 2020",
    "rt 2012": "RT 2012",
    "maitrise d'oeuvre": "Maîtrise d'œuvre",
    "maitrise d'ouvrage": "Maîtrise d'ouvrage",
    "suivi de chantier": "Suivi de chantier",
    "conduite de travaux": "Conduite de travaux",
    "rdm": "RDM",
    "resistance des materiaux": "Résistance des matériaux",
    # Sciences
    "pcr": "PCR",
    "hplc": "HPLC",
    "western blot": "Western blot",
    "biologie moleculaire": "Biologie moléculaire",
    "bioinformatique": "Bioinformatique",
    "gc-ms": "GC-MS",
    "rmn": "RMN",
    "bpl": "BPL",
    "analyse statistique": "Analyse statistique",
    # Enseignement
    "e-learning": "E-learning",
    "foad": "FOAD",
    "blended learning": "Blended learning",
    "classe inversee": "Classe inversée",
    "pedagogie active": "Pédagogie active",
    "tbi": "TBI",
    "ingenierie pedagogique": "Ingénierie pédagogique",
    # Logistique
    "sap mm": "SAP MM",
    "sap sd": "SAP SD",
    "sap wm": "SAP WM",
    "wms": "WMS",
    "tms": "TMS",
    "mrp": "MRP",
    "just in time": "Just-in-time",
    "jit": "Just-in-time",
    "lean manufacturing": "Lean Manufacturing",
    "six sigma": "Six Sigma",
    "kaizen": "Kaizen",
    "incoterms": "Incoterms",
    "import export": "Import-export",
    "import-export": "Import-export",
    # Agroalimentaire
    "haccp": "HACCP",
    "iso 22000": "ISO 22000",
    "ifs": "IFS",
    "brc": "BRC",
    "fssc 22000": "FSSC 22000",
    "bph": "BPH",
    "bpf": "BPF",
    "smq": "SMQ",
    "amdec": "AMDEC",
    "spc": "SPC",
    "msp": "MSP",
}


# ================================================================
# Regex pour détecter les années d'expérience associées à un skill
# ================================================================

_YEARS_PATTERN = re.compile(
    r"(\d{1,2})\s*(?:ans?|years?|an)\s*(?:d[e']?\s*)?(?:exp[ée]rience)?",
    re.IGNORECASE,
)

_SKILL_YEARS_CONTEXT = re.compile(
    r"(?:(\d{1,2})\s*(?:ans?|years?|an)\s*(?:d[e']?\s*)?(?:exp[ée]rience\s*)?(?:en\s*|de\s*|with\s*)?(.+?)(?:\n|,|;|$))"
    r"|(?:(.+?)\s*[\(\[:]\s*(\d{1,2})\s*(?:ans?|years?)\s*[\)\]:]?)",
    re.IGNORECASE,
)


def _infer_level(years: Optional[int]) -> str:
    """
    Infère le niveau d'expertise à partir des années d'expérience.

    Règles :
    - 0-2 ans  → Débutant
    - 3-5 ans  → Intermédiaire
    - 6-10 ans → Avancé
    - 10+ ans  → Expert
    """
    if years is None:
        return "Non spécifié"
    if years <= 2:
        return "Débutant"
    if years <= 5:
        return "Intermédiaire"
    if years <= 10:
        return "Avancé"
    return "Expert"


class SkillsExtractor:
    """
    Extracteur de compétences techniques.

    - Matching case-insensitive sur une base de 300+ compétences
    - Gestion des synonymes (JS → JavaScript, Postgres → PostgreSQL, etc.)
    - Extraction des années d'expérience associées par compétence
    - Inférence automatique du niveau (Débutant / Intermédiaire / Avancé / Expert)
    - [IA] Découverte de compétences inconnues via spaCy NER (entités MISC/ORG)
    """

    # Mots courants à exclure de la découverte NER (faux positifs fréquents)
    _NER_BLACKLIST = frozenset({
        # Mots FR courants
        "et", "ou", "de", "du", "des", "le", "la", "les", "un", "une",
        "en", "au", "aux", "par", "pour", "sur", "avec", "sans", "dans",
        "est", "sont", "avoir", "être", "faire", "tout", "tous",
        "experience", "expérience", "formation", "profil", "projet",
        "travail", "emploi", "poste", "stage", "missions", "mission",
        "résumé", "resume", "cv", "candidat", "recruteur",
        "bases", "outils", "langues", "langue", "langages", "langage",
        "mobile", "frontend", "backend", "stack", "full-stack", "fullstack",
        # Mois FR
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        "fevrier", "aout", "decembre",
        # Mois EN
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
        # Verbes d'action anglais (fréquents dans bullet points CV EN)
        "developed", "managed", "built", "designed", "led", "implemented",
        "deployed", "maintained", "created", "worked", "used", "utilized",
        "collaborated", "participated", "contributed", "supported", "helped",
        "analyzed", "tested", "wrote", "reviewed", "improved", "optimized",
        "delivered", "integrated", "migrated", "automated", "monitored",
        "configured", "installed", "upgraded", "documented", "trained",
        "responsible", "experience", "including", "using", "working",
        "based", "focused", "related", "various", "multiple", "different",
        "good", "strong", "excellent", "proficient", "familiar", "knowledge",
        "ability", "skills", "team", "project", "system", "application",
        "service", "platform", "solution", "environment", "development",
        "company", "organization", "business", "client", "customer",
        # Mots section CV
        "education", "work", "summary", "objective", "profile",
        "references", "interests", "hobbies", "activities", "awards",
        "certifications", "publications", "languages", "contact",
        # Chiffres et tokens parasites
        "present", "current", "ongoing", "today",
        # Écoles et universités connues (noms, pas des compétences)
        "esprit", "iset", "enit", "insat", "ensi", "fst", "fseg",
        "université", "universite", "faculté", "faculte", "école", "ecole",
        "institut", "lycée", "lycee", "campus", "university", "college",
        "school", "academy", "institute",
    })

    def __init__(self, nlp_model=None):
        # Construire un index inversé : nom_lower → (nom_canonique, catégorie)
        self._index: Dict[str, tuple] = {}
        for category, skills in SKILLS_DATABASE.items():
            for skill in skills:
                self._index[skill.lower()] = (skill, category)

        # Ajouter les synonymes dans l'index
        for alias, canonical in SYNONYMS.items():
            cat = self._find_category(canonical)
            self._index[alias.lower()] = (canonical, cat)

        # Trier les clés par longueur décroissante pour matcher les plus longues d'abord
        self._sorted_keys = sorted(self._index.keys(), key=len, reverse=True)

        # Modèle spaCy optionnel pour la découverte NER
        self._nlp = nlp_model

        # Cache fuzzy : liste plate des clés pour rapidfuzz (construite une seule fois)
        # On ne prend que les clés >= 4 chars pour éviter les faux positifs
        self._fuzzy_keys: List[str] = [k for k in self._index if len(k) >= 4]

    # Skills ambiguës (1-2 lettres) : nécessitent un contexte explicite
    # pour éviter les faux positifs ("C" dans "C'est", "R" dans "Responsable")
    _AMBIGUOUS_SKILLS = {"c", "r", "go"}

    # Contextes qui confirment "C" comme langage (case-sensitive pour certains)
    _C_CONTEXT_PATTERNS = [
        re.compile(r"\bC\s*/\s*C\+\+", re.IGNORECASE),
        re.compile(r"\bC\+\+"),
        re.compile(r"\blangage\s+C\b", re.IGNORECASE),
        re.compile(r"\bprogrammation\s+(?:en\s+)?C\b", re.IGNORECASE),
        re.compile(r"\bC\s+programming\b", re.IGNORECASE),
        re.compile(r"\bC\b(?:\s*,\s*(?:C\+\+|Python|Java|Go|Rust))", re.IGNORECASE),
        re.compile(r"(?:Python|Java|Go|Rust)\s*,\s*\bC\b", re.IGNORECASE),
        re.compile(r"\bC\s*[/|]\s*C#", re.IGNORECASE),
    ]

    # Contextes qui confirment "R" comme langage
    _R_CONTEXT_PATTERNS = [
        re.compile(r"\bR\s+Studio\b", re.IGNORECASE),
        re.compile(r"\blangage\s+R\b", re.IGNORECASE),
        re.compile(r"\bR\s+programming\b", re.IGNORECASE),
        re.compile(r"\bR\b(?:\s*,\s*(?:Python|Matlab|Julia|SPSS))", re.IGNORECASE),
        re.compile(r"(?:Python|Matlab|Julia|SPSS)\s*,\s*\bR\b", re.IGNORECASE),
        re.compile(r"\bstatistiques?\s+(?:avec|en)\s+R\b", re.IGNORECASE),
    ]

    # Contextes "Go" (pour éviter "go" verbe anglais)
    _GO_CONTEXT_PATTERNS = [
        re.compile(r"\bGolang\b", re.IGNORECASE),
        re.compile(r"\bGo\s+(?:lang|Language)\b", re.IGNORECASE),
        re.compile(r"\bGo\b(?:\s*,\s*(?:Rust|Python|Java|C\+\+))", re.IGNORECASE),
        re.compile(r"(?:Rust|Python|Java|C\+\+)\s*,\s*\bGo\b", re.IGNORECASE),
        re.compile(r"\bGo\b\s*[/|,]\s*(?:Gin|Fiber|Echo)", re.IGNORECASE),
    ]

    # Patterns pour détecter la section Compétences
    _SECTION_PATTERNS = re.compile(
        r"(?:^|\n)\s*(?:"
        r"comp[ée]tences"
        r"|comp[ée]tences\s+techniques"
        r"|comp[ée]tences\s+professionnelles"
        r"|comp[ée]tences\s+cl[ée]s"
        r"|comp[ée]tences?\s*(?:techniques?|professionnelles?|cl[ée]s?)?"
        r"|skills?\s*(?:&\s*)?(?:competenc(?:ies|es))?"
        r"|skills\s+and\s+tools"
        r"|technologies?\s*(?:utilis[ée]es?)?"
        r"|technologies?\s+et\s+outils?"
        r"|stack\s+technique"
        r"|stack"
        r"|outils?\s*(?:et\s+technologies?)?"
        r"|connaissances?\s*(?:techniques?)?"
        r"|savoir[\s\-]faire"
        r"|savoir\s+faire"
        r"|technical\s+skills?"
        r"|skills"
        r"|technical\s+skills"
        r"|hard\s+skills?"
        r"|core\s+(?:competenc(?:ies|es)|skills?)"
        r"|expertise"
        r")\s*[:\-–—]?\s*(?:\n|$)",
        re.IGNORECASE,
    )

    # Patterns de fin de section (prochaine section du CV)
    _NEXT_SECTION = re.compile(
        r"\n\s*(?:"
        r"exp[ée]rience|exp[ée]riences?\s*(?:professionnelles?)?"
        r"|parcours|emplois?|carri[èe]re"
        r"|formation[s]?|[ée]ducation|education"
        r"|langues?|languages?"
        r"|projets?\s*(?:personnels?|acad[ée]miques?)?"
        r"|certifications?"
        r"|loisirs?|hobbies?|centres?\s+d[''']int[ée]r[eê]ts?"
        r"|r[ée]f[ée]rences?"
        r"|profil|summary|objective|about"
        r"|work\s+experience|employment"
        r"|professional\s+experience"
        r"|divers"
        r")\s*[:\-–—]?\s*(?:\n|$)",
        re.IGNORECASE,
    )

    @staticmethod
    def _find_category(skill_name: str) -> str:
        """Trouve la catégorie d'une compétence."""
        low = skill_name.lower()
        for category, skills in SKILLS_DATABASE.items():
            for s in skills:
                if s.lower() == low:
                    return category
        return "autre"

    def _extract_years_for_skill(self, text: str, skill_name: str) -> Optional[int]:
        """
        Cherche dans le texte une mention d'années d'expérience liée à la compétence.
        Exemples détectés :
        - "7 ans d'expérience en Python"
        - "Python (5 ans)"
        - "Python : 3 ans"
        """
        patterns = [
            # "X ans d'expérience en <skill>"
            re.compile(
                rf"(\d{{1,2}})\s*(?:ans?|years?)\s*(?:d[e']?\s*)?(?:exp[ée]rience\s*)?(?:en|de|with|in)?\s*{re.escape(skill_name)}",
                re.IGNORECASE,
            ),
            # "<skill> (X ans)" ou "<skill> : X ans"
            re.compile(
                rf"{re.escape(skill_name)}\s*[\(\[:–\-]\s*(\d{{1,2}})\s*(?:ans?|years?)",
                re.IGNORECASE,
            ),
            # "<skill>, X ans"
            re.compile(
                rf"{re.escape(skill_name)}\s*,\s*(\d{{1,2}})\s*(?:ans?|years?)",
                re.IGNORECASE,
            ),
        ]

        for pat in patterns:
            m = pat.search(text)
            if m:
                return int(m.group(1))

        return None

    def _is_ambiguous_confirmed(self, key: str, text: str) -> bool:
        """Vérifie si une skill ambiguë (C, R, Go) est confirmée par le contexte."""
        if key == "c":
            return any(p.search(text) for p in self._C_CONTEXT_PATTERNS)
        if key == "r":
            return any(p.search(text) for p in self._R_CONTEXT_PATTERNS)
        if key == "go":
            return any(p.search(text) for p in self._GO_CONTEXT_PATTERNS)
        return True

    def _extract_skills_section(self, text: str) -> Optional[str]:
        """Isole la section Compétences/Skills du CV.

        Returns:
            Le texte de la section, ou None si non trouvée.
        """
        m = self._SECTION_PATTERNS.search(text)
        if not m:
            # Fallback inline (ex: "SAVOIR-FAIRE Recrutement ...")
            m = re.search(
                r"\b(?:comp[ée]tences?|skills?|savoir[\s\-]faire|"
                r"connaissances?|technologies?|outils?|stack\s+technique)\b",
                text,
                re.IGNORECASE,
            )
            if not m:
                return None

        start = m.end()
        next_sec = self._NEXT_SECTION.search(text[start:])
        if next_sec:
            section = text[start:start + next_sec.start()]
        else:
            section = text[start:]

        # Limiter à 3000 chars max (sécurité)
        return section[:3000]

    def _search_skills_in_text(self, text: str, text_original: str) -> Dict[str, Dict]:
        """Cherche les skills dans un texte donné.

        Args:
            text: Texte (lowered) à scanner.
            text_original: Texte original (pour contexte case-sensitive).

        Returns:
            dict: canonical_lower → skill_info
        """
        found: Dict[str, Dict] = {}

        for key in self._sorted_keys:
            canonical, category = self._index[key]
            canon_lower = canonical.lower()

            if canon_lower in found:
                continue

            # Protection skills ambiguës
            if key in self._AMBIGUOUS_SKILLS:
                if not self._is_ambiguous_confirmed(key, text_original):
                    continue

            # Word-boundary matching
            escaped = re.escape(key)
            if key[-1].isalnum():
                pattern = rf"(?<![a-zA-Z0-9]){escaped}\b"
            else:
                pattern = rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])"

            if not re.search(pattern, text):
                continue

            found[canon_lower] = {
                "name": canonical,
                "category": category,
            }

        return found

    # ================================================================
    # FUZZY MATCHING — Détection des fautes de frappe
    # "Pyhton" → "Python", "Djnago" → "Django", "Reactjs" → "React"
    # ================================================================

    # Seuil de similarité : 88% évite les faux positifs tout en couvrant
    # les fautes courantes (1-2 lettres, transpositions, lettres manquantes)
    _FUZZY_THRESHOLD = 82

    # Skills trop courtes pour fuzzy (risque de faux positifs trop élevé)
    _FUZZY_MIN_LEN = 4

    def _extract_fuzzy_skills(
        self, section_text: str, already_found: Set[str]
    ) -> List[Dict]:
        """
        [IA — Fuzzy Matching] Détecte les compétences mal orthographiées.

        Utilise rapidfuzz (distance de Levenshtein optimisée) pour trouver
        les tokens du CV qui ressemblent à une compétence connue même avec
        une faute de frappe.

        Exemples :
        - "Pyhton"   → Python  (score 91%)
        - "Djnago"   → Django  (score 89%)
        - "Reactjs"  → React   (score 86%)
        - "postgress" → PostgreSQL (score 88%)

        Seules les correspondances >= _FUZZY_THRESHOLD sont acceptées.
        """
        if not _RAPIDFUZZ_AVAILABLE or not section_text:
            return []

        discovered: List[Dict] = []
        seen: Set[str] = set(already_found)

        # Extraire les tokens bruts de la section (séparateurs standards)
        raw_tokens = re.split(r"[,|;•·\n\r/\s]+", section_text)

        for token in raw_tokens:
            token = token.strip(" \t-–—*►▪◆○●()")
            token_lower = token.lower()

            # Filtres de base
            if len(token) < self._FUZZY_MIN_LEN or len(token) > 40:
                continue
            if token_lower in seen:
                continue
            if token_lower in self._index:
                continue  # déjà trouvé par matching exact
            if not re.search(r"[A-Za-zÀ-ÿ]", token):
                continue
            if re.fullmatch(r"[\d\s\-/\.]+", token):
                continue

            # Recherche fuzzy dans les clés du dictionnaire
            result = _fuzz_process.extractOne(
                token_lower,
                self._fuzzy_keys,
                scorer=_fuzz.WRatio,
                score_cutoff=self._FUZZY_THRESHOLD,
            )

            if result is None:
                continue

            matched_key, score, _ = result
            canonical, category = self._index[matched_key]
            canon_lower = canonical.lower()

            if canon_lower in seen:
                continue

            seen.add(canon_lower)
            discovered.append({
                "name": canonical,       # On retourne le nom CORRECT du dictionnaire
                "category": category,
                "source": "fuzzy",
                "original_token": token, # Le token original (avec faute)
                "fuzzy_score": round(score, 1),
                "years": None,
                "level": "Non spécifié",
            })
            logger.info(
                "[Fuzzy] '%s' → '%s' (score=%.0f%%)",
                token, canonical, score,
            )

        if discovered:
            logger.info(
                "[Fuzzy] %d compétences corrigées : %s",
                len(discovered),
                [(s["original_token"], "→", s["name"]) for s in discovered],
            )
        return discovered

    def _extract_ner_skills(self, section_text: str, already_found: set) -> List[Dict]:
        """
        [IA — Option B] Découverte de compétences inconnues via spaCy NER.

        Exécute le pipeline NER spaCy sur le texte de la section Compétences
        et extrait les entités MISC/ORG qui ne sont pas déjà dans le dictionnaire.
        Ces entités sont des outils, frameworks ou technologies non répertoriés.

        Args:
            section_text: Texte de la section compétences isolée.
            already_found: Set des noms (lower) déjà trouvés par matching dictionnaire.

        Returns:
            Liste de skills {"name", "category", "source", "years", "level"}
        """
        if self._nlp is None:
            return []

        has_ner = getattr(self._nlp, "has_pipe", lambda _: False)("ner")
        if not has_ner:
            return []

        discovered = []
        seen_lower: set = set(already_found)

        try:
            # Limiter à 2000 chars pour performance
            doc = self._nlp(section_text[:2000])
            for ent in doc.ents:
                if ent.label_ not in ("MISC", "ORG"):
                    continue

                name = ent.text.strip()
                name_lower = name.lower()

                # Filtres qualité
                if len(name) < 3:
                    continue
                # Nettoyer les préfixes collés type "lISET" → "ISET", "dESPRIT" → "ESPRIT"
                # Artefact PDF double-colonne : "de l'ISET" → "lISET" après extraction
                name = re.sub(r"^[a-zàâéèêëîïôùûü]{1,2}(?=[A-ZÀÂÉÈÊÏÎÔÙÛÜ])", "", name)
                name_lower = name.lower()
                if len(name) < 3:
                    continue
                if name_lower in self._NER_BLACKLIST:
                    continue
                # Vérifier aussi si un token du nom est dans la blacklist (ex: "ISET Nabeul" → "iset" blacklisté)
                if any(tok.lower() in self._NER_BLACKLIST for tok in name.split()):
                    continue
                if name_lower in seen_lower:
                    continue
                # Rejeter si contient un saut de ligne (artefact double colonne)
                if "\n" in name:
                    continue
                # Rejeter si contient uniquement des chiffres/ponctuation
                if not re.search(r"[a-zA-ZÀ-ÿ]", name):
                    continue
                # Rejeter si ressemble à une date ou un nombre
                if re.fullmatch(r"\d[\d\s\-/]+\d", name):
                    continue
                # Rejeter si mot unique trop générique (< 4 chars ou dans blacklist)
                if len(name) < 4 and not re.search(r"[A-Z]{2,}", name):
                    continue
                # Rejeter si contient un mot de ville/pays connu (artefact géographique)
                _GEO_TOKENS = {"nabeul", "tunis", "sfax", "sousse", "monastir", "bizerte",
                               "ariana", "ben", "arous", "manouba", "france", "paris",
                               "lyon", "marseille", "algerie", "maroc", "tunisie"}
                if any(tok.lower() in _GEO_TOKENS for tok in name.split()):
                    continue

                seen_lower.add(name_lower)
                discovered.append({
                    "name": name,
                    "category": "découverte_ia",
                    "source": "spacy_ner",
                    "years": None,
                    "level": "Non spécifié",
                })

        except Exception as e:
            logger.warning("NER skill discovery failed: %s", e)

        if discovered:
            logger.info(
                "[NER] %d compétences découvertes hors dictionnaire : %s",
                len(discovered),
                [s["name"] for s in discovered],
            )

        return discovered

    # Patterns pour capturer des compétences inconnues sans NER
    _CAMEL_CASE_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
    _DOTTED_NAME_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9]+(?:\.[A-Za-z][A-Za-z0-9]+)+\b")
    _VERSIONED_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9\+#\-\.]{2,})\s+v?\d+(?:\.\d+)*\b")
    _SLASH_TECH_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:/[A-Z][A-Za-z0-9]+)+\b")
    _ALLCAPS_PATTERN = re.compile(r"\b[A-Z]{2,10}\b")
    # Tokens à ignorer dans les patterns (trop génériques ou mots courants)
    _PATTERN_BLACKLIST = frozenset({
        "AND", "OR", "NOT", "THE", "FOR", "WITH", "FROM", "INTO", "OVER",
        "THIS", "THAT", "HAVE", "BEEN", "WILL", "ALSO", "SOME", "BOTH",
        "API", "SDK", "CLI", "GUI", "URL", "URI", "HTTP", "HTTPS", "REST",
        "SQL", "CSV", "XML", "PDF", "HTML", "CSS", "JSON",
        "CV", "RH", "HR", "IT",
        "I", "II", "III", "IV", "VI", "VII",
    })

    def _extract_pattern_skills(self, section_text: str, already_found: set) -> List[Dict]:
        """
        Découverte de compétences inconnues par patterns lexicaux sur la section Compétences.

        Cible :
        - CamelCase : NextAuth, FlutterFlow, TanStack
        - Noms pointés : Vue.js, .NET, Node.js
        - Noms versionnés : Python 3.11, Node 18
        - Abréviations MAJUSCULES contextuelles : ORM, MVC, CQRS
        - Slash tech : CI/CD, REST/gRPC

        Ne remplace pas le NER — complémentaire pour les CVs EN.
        """
        discovered: List[Dict] = []
        seen_lower = set(already_found)

        candidates: List[str] = []

        # CamelCase (ex: NextAuth, FlutterFlow, TailwindCSS)
        candidates += self._CAMEL_CASE_PATTERN.findall(section_text)
        # Noms avec points (ex: Vue.js, Node.js, .NET)
        candidates += self._DOTTED_NAME_PATTERN.findall(section_text)
        # Noms versionnés — extraire le nom sans la version
        for m in self._VERSIONED_PATTERN.finditer(section_text):
            candidates.append(m.group(1))
        # Slash tech (ex: REST/gRPC, CI/CD déjà dans dict mais d'autres peuvent passer)
        candidates += self._SLASH_TECH_PATTERN.findall(section_text)
        # MAJUSCULES courtes (ex: ORM, MVC, CQRS, gRPC)
        for m in self._ALLCAPS_PATTERN.finditer(section_text):
            word = m.group(0)
            if word not in self._PATTERN_BLACKLIST:
                candidates.append(word)

        for name in candidates:
            name = name.strip()
            name_lower = name.lower()
            if len(name) < 2:
                continue
            if name_lower in seen_lower:
                continue
            if name_lower in self._NER_BLACKLIST:
                continue
            if name in self._PATTERN_BLACKLIST:
                continue
            if "\n" in name:
                continue
            # Rejeter les mots purement courants (lowercase = mot anglais courant)
            if name.islower() and len(name) < 6:
                continue
            seen_lower.add(name_lower)
            discovered.append({
                "name": name,
                "category": "découverte_ia",
                "source": "pattern",
                "years": None,
                "level": "Non spécifié",
            })

        if discovered:
            logger.debug(
                "[PATTERN] %d compétences découvertes par patterns : %s",
                len(discovered),
                [s["name"] for s in discovered],
            )
        return discovered

    # ================================================================
    # SOLUTION 1 — Extraction par contexte de section
    # Tout token listé dans la section Skills est candidat compétence
    # ================================================================

    # Mots courants FR/EN à ne pas extraire comme compétences
    _CONTEXT_BLACKLIST: Set[str] = frozenset({
        "les", "des", "une", "and", "the", "for", "with", "vous", "nous",
        "bonne", "bons", "sens", "gout", "goût", "esprit", "capacite",
        "solide", "forte", "base", "bases", "avance", "avancé", "niveau",
        "maîtrise", "maitrise", "connaissance", "connaissances", "utilisation",
        "développement", "developpement", "gestion", "analyse", "conception",
        "mise", "place", "travail", "equipe", "équipe", "communication",
        "rigueur", "autonomie", "organisation", "adaptabilite", "creativite",
        "problem", "solving", "oriented", "driven", "based", "management",
        "experience", "expérience", "ans", "années", "mois",
    })

    def _extract_section_context_skills(
        self, section_text: str, already_found: Set[str]
    ) -> List[Dict]:
        """
        [Solution 1] Extrait TOUT token listé dans la section Skills.

        Principe : dans une section Compétences, les éléments séparés
        par virgules, pipes, bullets, sauts de ligne SONT des compétences,
        même si elles ne sont pas dans le dictionnaire.

        Ex: "Python, MonFrameworkInconnu, XYZ v3" → extrait les 3.
        """
        if not section_text:
            return []

        discovered: List[Dict] = []
        seen: Set[str] = set(already_found)

        # Séparateurs courants dans les sections de compétences
        # On split sur : virgule, pipe, point-virgule, bullet, saut de ligne
        raw_tokens = re.split(r"[,|;•·\n\r/]", section_text)

        for token in raw_tokens:
            # Nettoyer
            token = token.strip(" \t-–—*►▪◆○●")
            token = re.sub(r"\s+", " ", token).strip()

            # Longueur raisonnable pour une compétence (2-40 chars)
            if len(token) < 2 or len(token) > 40:
                continue

            # Doit contenir au moins une lettre
            if not re.search(r"[A-Za-zÀ-ÿ]", token):
                continue

            # Ignorer les tokens trop génériques
            token_lower = token.lower()
            if token_lower in self._CONTEXT_BLACKLIST:
                continue

            # Ignorer les tokens qui sont des phrases (> 3 mots)
            words = token.split()
            if len(words) > 3:
                continue

            # Ignorer les syntagmes nominaux français : "Production de contenus X"
            # (2e mot = préposition → phrase, pas une compétence)
            if len(words) >= 2 and words[1].lower() in {
                "de", "des", "du", "la", "le", "les", "a", "aux", "en",
                "par", "pour", "sur", "avec", "sans", "dans", "et", "ou"
            }:
                continue

            # Ignorer les lignes de section ou d'éducation
            if re.search(
                r"compétences?|skills?|techniques?|outils?|tools?"
                r"|baccalauréat|baccalaureat|licence|master|diplôme|diplome"
                r"|activités?|activites?|académique|academique|extra"
                r"|tunisie|france|maroc|algerie|paris|tunis",
                token_lower
            ):
                continue

            # Ignorer si contient des mots de géographie courants
            _GEO = {"tunisie", "france", "maroc", "algerie", "paris", "tunis",
                    "sfax", "sousse", "ariana", "nabeul"}
            if any(g in token_lower.split() for g in _GEO):
                continue

            # Ignorer si déjà trouvé
            if token_lower in seen:
                continue

            # Ignorer si c'est juste un nombre ou date
            if re.fullmatch(r"[\d\s\-/\.]+", token):
                continue

            seen.add(token_lower)
            discovered.append({
                "name": token,
                "category": "découverte_contexte",
                "source": "section_context",
                "years": None,
                "level": "Non spécifié",
            })

        if discovered:
            logger.info(
                "[Solution1-Contexte] %d compétences extraites du contexte de section",
                len(discovered),
            )
        return discovered

    # ================================================================
    # SOLUTION 2 — Co-occurrence sémantique
    # Un token inconnu qui apparaît dans le même cluster qu'une
    # compétence connue est probablement lui-même une compétence.
    # Complété par similarité spaCy si des vecteurs sont disponibles.
    # ================================================================

    # Mots de liaison à rejeter même en co-occurrence
    _COOC_STOP = frozenset({
        "and", "or", "with", "for", "the", "a", "an", "to", "of", "in",
        "et", "ou", "de", "du", "des", "la", "le", "les", "un", "une",
        "en", "au", "aux", "par", "pour", "sur", "avec", "sans", "dans",
        "autres", "autre", "divers", "divers", "various", "including",
    })

    def _cluster_has_known_skill(self, cluster_lower: str) -> bool:
        """Retourne True si au moins 1 compétence connue est présente dans le cluster."""
        for k in self._sorted_keys:
            if len(k) < 3:
                continue
            escaped = re.escape(k)
            if re.search(rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])", cluster_lower):
                return True
        return False

    def _extract_word2vec_skills(
        self, section_text: str, already_found: Set[str]
    ) -> List[Dict]:
        """
        [Solution 2 — IA] Découverte par co-occurrence sémantique.

        Principe : dans une section Compétences, les termes listés dans
        le même cluster (ligne / bullet) qu'une compétence connue sont
        eux-mêmes très probablement des compétences techniques.

        Exemple :
          "Python, FastAPI, MonNouveauFramework, XYZ"
          → "Python" est connu → "MonNouveauFramework" et "XYZ" sont candidats.

        Complément : si fr_core_news_md a des vecteurs word2vec, on ajoute
        une vérification de similarité cosinus (seuil 0.65) pour les tokens
        non couverts par la co-occurrence.
        """
        discovered: List[Dict] = []
        seen: Set[str] = set(already_found)

        if not section_text:
            return discovered

        # ── Passe 1 : Co-occurrence locale ────────────────────────────────────
        # Découper la section en clusters (ligne ou bullet ou pipe)
        clusters = re.split(r"[\n\r|•·►▪●◆]", section_text)

        for cluster in clusters:
            cluster = cluster.strip()
            if not cluster:
                continue

            cluster_lower = cluster.lower()

            # Ignorer les clusters trop courts ou trop longs
            if len(cluster) < 4 or len(cluster) > 300:
                continue

            # Ce cluster contient-il au moins 1 skill connu ?
            if not self._cluster_has_known_skill(cluster_lower):
                continue

            # Oui → extraire les tokens séparés par virgules/points-virgules
            items = re.split(r"[,;/]", cluster)
            for item in items:
                item = item.strip(" \t-–—*►▪◆○●")
                item = re.sub(r"\s+", " ", item).strip()
                if not item:
                    continue

                item_lower = item.lower()

                # Filtres basiques
                if len(item) < 2 or len(item) > 40:
                    continue
                if item_lower in seen:
                    continue
                if item_lower in self._CONTEXT_BLACKLIST:
                    continue
                if item_lower in self._COOC_STOP:
                    continue
                if item_lower in self._NER_BLACKLIST:
                    continue
                if not re.search(r"[A-Za-zÀ-ÿ]", item):
                    continue
                if re.fullmatch(r"[\d\s\-/\.]+", item):
                    continue

                words = item.split()
                # Rejeter les phrases > 3 mots
                if len(words) > 3:
                    continue
                # Rejeter syntagmes nominaux français (2e mot = préposition)
                if len(words) >= 2 and words[1].lower() in {
                    "de", "des", "du", "la", "le", "les", "a", "aux",
                    "en", "par", "pour", "sur", "avec", "sans", "dans", "et", "ou"
                }:
                    continue

                # Vérifier que l'item n'est pas lui-même une compétence déjà dans l'index
                # (on ne veut pas redécouvrir ce qu'on a déjà)
                if item_lower in self._index:
                    continue

                # Doit ressembler à un terme technique :
                # - commence par une majuscule, OU
                # - est tout en majuscules (acronyme), OU
                # - contient un chiffre collé (ex: Node18, Python3), OU
                # - contient un point/tiret typique des noms tech (Vue.js, Next-gen)
                is_tech_like = (
                    (item[0].isupper())
                    or (item.isupper() and len(item) >= 2)
                    or bool(re.search(r"[A-Za-z]\d|\d[A-Za-z]", item))
                    or bool(re.search(r"[A-Za-z][.\-+#][A-Za-z]", item))
                )
                if not is_tech_like:
                    continue

                seen.add(item_lower)
                discovered.append({
                    "name": item,
                    "category": "découverte_ia",
                    "source": "word2vec",
                    "years": None,
                    "level": "Non spécifié",
                    "similarity_score": 0.85,  # Co-occurrence directe → confiance haute
                })

        # ── Passe 2 : Similarité cosinus spaCy (complément) ──────────────────
        # Uniquement si le modèle a des vecteurs (fr_core_news_md / md/lg)
        if self._nlp is not None and self._nlp.vocab.vectors.shape[0]:
            # Vecteurs de référence : skills connues qui ont un vecteur
            reference_skills: Dict[str, str] = {}
            for cat, skills in SKILLS_DATABASE.items():
                for skill in skills[:8]:
                    tok = self._nlp.vocab[skill.lower()]
                    if tok.has_vector:
                        reference_skills[skill.lower()] = cat

            if reference_skills:
                SIMILARITY_THRESHOLD = 0.65  # Seuil abaissé (plus de rappel)
                try:
                    doc = self._nlp(section_text[:2000])
                except Exception:
                    doc = None

                if doc is not None:
                    for token in doc:
                        if token.is_punct or token.is_space or not token.has_vector:
                            continue
                        if len(token.text) < 3:
                            continue
                        token_lower = token.text.lower()
                        if token_lower in seen:
                            continue
                        if token_lower in self._CONTEXT_BLACKLIST:
                            continue
                        if token.is_stop:
                            continue
                        if token_lower in self._index:
                            continue

                        best_sim = 0.0
                        best_cat = "découverte_ia"
                        for ref_skill, ref_cat in reference_skills.items():
                            ref_tok = self._nlp.vocab[ref_skill]
                            sim = token.similarity(ref_tok)
                            if sim > best_sim:
                                best_sim = sim
                                best_cat = ref_cat

                        if best_sim >= SIMILARITY_THRESHOLD:
                            seen.add(token_lower)
                            discovered.append({
                                "name": token.text,
                                "category": best_cat,
                                "source": "word2vec",
                                "years": None,
                                "level": "Non spécifié",
                                "similarity_score": round(best_sim, 3),
                            })

        if discovered:
            logger.info(
                "[Solution2-CoOccurrence] %d compétences découvertes : %s",
                len(discovered),
                [s["name"] for s in discovered[:8]],
            )
        return discovered

    # ================================================================
    # SOLUTION 3 — Dictionnaire auto-enrichi
    # Sauvegarde des nouvelles découvertes pour enrichir au fil du temps
    # ================================================================

    _DISCOVERED_FILE = (
        Path(__file__).resolve().parents[4] / "data" / "skills_discovered.json"
    )

    def _load_discovered_skills(self) -> Dict[str, str]:
        """Charge le dictionnaire auto-enrichi (découvertes passées)."""
        try:
            if self._DISCOVERED_FILE.exists():
                data = json.loads(self._DISCOVERED_FILE.read_text(encoding="utf-8"))
                return data  # {"nom_lower": "catégorie"}
        except Exception as e:
            logger.warning("[Solution3] Impossible de charger skills_discovered.json : %s", e)
        return {}

    def _save_discovered_skills(self, new_skills: List[Dict]) -> None:
        """
        Ajoute les nouvelles découvertes au dictionnaire persistant.
        Ne sauvegarde que les découvertes de qualité (source != general).
        """
        if not new_skills:
            return
        try:
            # Charger existant
            existing = self._load_discovered_skills()

            # Ajouter les nouvelles découvertes (section_context, word2vec, spacy_ner)
            added = 0
            for skill in new_skills:
                name_lower = skill["name"].lower()
                if name_lower not in existing and skill.get("source") in (
                    "section_context", "word2vec", "spacy_ner"
                ):
                    existing[name_lower] = skill.get("category", "découverte_ia")
                    added += 1

            if added > 0:
                self._DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
                self._DISCOVERED_FILE.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info("[Solution3] %d nouvelles compétences sauvegardées", added)
        except Exception as e:
            logger.warning("[Solution3] Impossible de sauvegarder : %s", e)

    def extract(self, text: str) -> Dict:
        """
        Extrait les compétences trouvées dans le texte.

        Stratégie pondérée :
        1. Isoler la section Compétences → chercher skills (source: section)
        2. Chercher dans le texte entier (source: general)
        3. Fusionner en gardant la source la plus fiable
        4. [IA] Découvrir des compétences inconnues via spaCy NER (section uniquement)
        5. [IA] Découvrir des compétences inconnues via patterns lexicaux (section uniquement)
        6. [Solution 1] Extraction par contexte de section (tout token listé)
        7. [Solution 2] Similarité Word2Vec (vecteurs spaCy)
        8. [Solution 3] Sauvegarder les nouvelles découvertes

        Returns:
            {
                "skills": [
                    {
                        "name": "Python",
                        "category": "langages",
                        "years": 5,
                        "level": "Intermédiaire",
                        "source": "section"
                    },
                    ...
                ],
                "by_category": {
                    "langages": ["Python", "Java"],
                    ...
                },
                "total_skills": 12
            }
        """
        if not text:
            return {"skills": [], "by_category": {}, "total_skills": 0}

        text_lower = text.lower()

        # Phase 1 : Chercher dans la section Compétences (haute confiance)
        section_text = self._extract_skills_section(text)
        section_skills: Dict[str, Dict] = {}
        if section_text:
            logger.debug(f"Section compétences trouvée ({len(section_text)} chars)")
            section_skills = self._search_skills_in_text(
                section_text.lower(), section_text
            )
            for info in section_skills.values():
                info["source"] = "section"
            logger.info(f"{len(section_skills)} skills trouvées dans section Compétences")

        # Phase 2 : Chercher dans tout le texte (confiance plus faible)
        all_skills = self._search_skills_in_text(text_lower, text)
        for info in all_skills.values():
            if info["name"].lower() not in section_skills:
                info["source"] = "general"

        # Phase 3 : Fusionner (section a priorité)
        merged: Dict[str, Dict] = {}
        for key, info in all_skills.items():
            if key in section_skills:
                merged[key] = section_skills[key]
            else:
                merged[key] = info
        # Ajouter les skills section qui n'étaient pas dans all_skills
        for key, info in section_skills.items():
            if key not in merged:
                merged[key] = info

        # Phase 4 : Enrichir avec années + niveaux
        for info in merged.values():
            years = self._extract_years_for_skill(text, info["name"])
            info["years"] = years
            info["level"] = _infer_level(years)

        # Phase 5 : [IA] Découverte NER — compétences hors dictionnaire
        ner_discoveries: List[Dict] = []
        already_found_set = set(merged.keys())
        if section_text and self._nlp is not None:
            ner_discoveries = self._extract_ner_skills(section_text, already_found_set)

        # Phase 6 : [IA] Découverte par patterns lexicaux (CamelCase, versionnés, etc.)
        pattern_discoveries: List[Dict] = []
        if section_text:
            already_for_pattern = already_found_set | {d["name"].lower() for d in ner_discoveries}
            pattern_discoveries = self._extract_pattern_skills(section_text, already_for_pattern)

        # Construire les résultats de base
        skills_list = sorted(merged.values(), key=lambda s: s["name"].lower())

        # Déduplication globale — le dictionnaire est prioritaire
        dict_names_lower = {s["name"].lower() for s in skills_list}

        def _dedup_discoveries(discoveries: List[Dict]) -> List[Dict]:
            result = []
            for disc in discoveries:
                disc_lower = disc["name"].lower()
                if disc_lower in dict_names_lower:
                    continue
                # Substring dedup : seulement si les deux termes sont
                # suffisamment longs pour éviter "sql" ⊂ "postgresql"
                if any(
                    (disc_lower in existing or existing in disc_lower)
                    and len(min(disc_lower, existing, key=len)) >= 5
                    for existing in dict_names_lower
                ):
                    continue
                result.append(disc)
                dict_names_lower.add(disc_lower)
                # Si fuzzy a corrigé une faute, bloquer aussi le token original
                # pour que section_context ne le ré-ajoute pas tel quel
                orig = disc.get("original_token")
                if orig:
                    dict_names_lower.add(orig.lower())
            return result

        ner_deduped = _dedup_discoveries(ner_discoveries)

        # ── Fuzzy matching : détection fautes de frappe ───────────────────────
        # Tourne avant pattern/contexte pour corriger les typos et bloquer
        # le token original (ex. "JavaScrip") avant qu'il soit capturé tel quel.
        fuzzy_discoveries: List[Dict] = []
        if section_text:
            already_fuzzy = dict_names_lower.copy()
            fuzzy_discoveries = _dedup_discoveries(
                self._extract_fuzzy_skills(section_text, already_fuzzy)
            )

        pattern_deduped = _dedup_discoveries(pattern_discoveries)

        # ── Solution 1 : Extraction par contexte de section ───────────────────
        context_discoveries: List[Dict] = []
        if section_text:
            already_ctx = dict_names_lower.copy()
            context_discoveries = _dedup_discoveries(
                self._extract_section_context_skills(section_text, already_ctx)
            )

        # ── Solution 2 : Similarité Word2Vec ──────────────────────────────────
        word2vec_discoveries: List[Dict] = []
        if section_text and self._nlp is not None:
            already_w2v = dict_names_lower.copy()
            word2vec_discoveries = _dedup_discoveries(
                self._extract_word2vec_skills(section_text, already_w2v)
            )

        # Assembler toutes les découvertes
        all_discoveries = (
            ner_deduped + pattern_deduped + fuzzy_discoveries
            + context_discoveries + word2vec_discoveries
        )
        skills_list = skills_list + all_discoveries

        # ── Solution 3 : Sauvegarder les nouvelles découvertes ────────────────
        self._save_discovered_skills(all_discoveries)

        by_category: Dict[str, List[str]] = {}
        for sk in skills_list:
            cat = sk["category"]
            by_category.setdefault(cat, []).append(sk["name"])

        logger.info(
            "Extraction terminée : %d skills "
            "(%d section, %d général, %d ner, %d pattern, %d contexte, %d word2vec, %d fuzzy)",
            len(skills_list),
            sum(1 for s in skills_list if s.get("source") == "section"),
            sum(1 for s in skills_list if s.get("source") == "general"),
            len(ner_deduped),
            len(pattern_deduped),
            len(context_discoveries),
            len(word2vec_discoveries),
            len(fuzzy_discoveries),
        )

        return {
            "skills": skills_list,
            "by_category": by_category,
            "total_skills": len(skills_list),
            "ner_discoveries": len(ner_deduped) + len(pattern_deduped),
            "context_discoveries": len(context_discoveries),
            "word2vec_discoveries": len(word2vec_discoveries),
            "fuzzy_discoveries": len(fuzzy_discoveries),
        }
