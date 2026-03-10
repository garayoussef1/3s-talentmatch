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

import logging
import re
from typing import Dict, List, Optional

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
        "HTML", "CSS", "SASS", "SCSS", "LESS",
    ],
    "frameworks_web": [
        "React", "Angular", "Vue.js", "Vue", "Svelte", "Next.js",
        "Nuxt.js", "Gatsby", "Remix", "Astro",
        "Django", "Flask", "FastAPI", "Express", "Express.js",
        "NestJS", "Spring", "Spring Boot", "Laravel", "Symfony",
        "Ruby on Rails", "Rails", "ASP.NET", ".NET", ".NET Core",
        "Gin", "Fiber", "Echo", "Actix", "Rocket",
        "Struts", "Play Framework", "Quarkus", "Micronaut",
        "Node.js", "Qt", "Bootstrap", "Tailwind CSS",
    ],
    "frameworks_mobile": [
        "React Native", "Flutter", "FlutterFlow", "SwiftUI", "Jetpack Compose",
        "Xamarin", "Ionic", "Cordova", "Capacitor", "Kivy",
        "NativeScript",
    ],
    "bases_de_donnees": [
        "PostgreSQL", "Postgres", "MySQL", "MariaDB", "Oracle",
        "SQL Server", "SQLite", "MongoDB", "Redis", "Cassandra",
        "DynamoDB", "CouchDB", "Neo4j", "InfluxDB", "Elasticsearch",
        "Firebase", "Firestore", "Supabase", "Memcached",
        "TimescaleDB", "CockroachDB", "ClickHouse",
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
    ],
    "outils_dev": [
        "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
        "VS Code", "IntelliJ", "Eclipse", "PyCharm", "WebStorm",
        "Jira", "Confluence", "Trello", "Notion", "Asana",
        "Postman", "Insomnia", "Swagger", "OpenAPI",
        "Webpack", "Vite", "Babel", "ESLint", "Prettier",
        "npm", "yarn", "pnpm", "pip", "Maven", "Gradle",
        "CMake", "Make", "Bazel",
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
    ],
    "securite": [
        "OWASP", "Burp Suite", "Metasploit", "Nmap", "Wireshark",
        "Nessus", "Snort", "Suricata", "Kali Linux",
        "SSL/TLS", "OAuth", "OAuth2", "JWT", "SAML",
        "LDAP", "Active Directory", "Keycloak",
        "Cryptographie", "Pentesting", "Firewall",
    ],
    "systemes_reseaux": [
        "Linux", "Ubuntu", "Debian", "CentOS", "Red Hat", "RHEL",
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
        "Gestion budgétaire", "Contrôle de gestion", "Tableau de bord",
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
        "Onboarding", "Intégration", "Parcours d'intégration",
        "Gestion paie", "Paie", "Charges sociales",
        "Relations sociales", "Droit du travail", "Négociation syndicale",
        "Formation", "Plan de formation", "CPF", "OPCO",
        "Entretiens", "Entretien annuel", "Entretien professionnel",
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
    # Node.js
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    # Mobile
    "flutterflow": "FlutterFlow",
    "flutter flow": "FlutterFlow",
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
    "tableau de bord": "Tableau de bord",
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
    "integration": "Intégration",
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
    """

    def __init__(self):
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

    def extract(self, text: str) -> Dict:
        """
        Extrait les compétences trouvées dans le texte.

        Stratégie pondérée :
        1. Isoler la section Compétences → chercher skills (source: section)
        2. Chercher dans le texte entier (source: general)
        3. Fusionner en gardant la source la plus fiable

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

        # Construire les résultats
        skills_list = sorted(merged.values(), key=lambda s: s["name"].lower())

        by_category: Dict[str, List[str]] = {}
        for sk in skills_list:
            cat = sk["category"]
            by_category.setdefault(cat, []).append(sk["name"])

        logger.info(
            f"Extraction terminée : {len(skills_list)} skills "
            f"({sum(1 for s in skills_list if s.get('source') == 'section')} section, "
            f"{sum(1 for s in skills_list if s.get('source') == 'general')} général)"
        )

        return {
            "skills": skills_list,
            "by_category": by_category,
            "total_skills": len(skills_list),
        }
