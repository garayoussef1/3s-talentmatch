"""
Profils de domaine pour le système d'entretien IA.
Chaque profil définit : persona recruteur, zones techniques, scénarios,
vocabulaire attendu, green/red flags, et focus d'évaluation.

Utilisé par groq_interview_service.py pour personnaliser les questions
selon le domaine de l'offre (JobOffer.domaine_metier).
"""

DOMAIN_PROFILES: dict = {

    # ══════════════════════════════════════════════════════
    # IT / DÉVELOPPEMENT LOGICIEL
    # ══════════════════════════════════════════════════════
    "IT / Développement": {
        "expert_persona": (
            "architecte logiciel senior avec 20 ans d'expérience en développement enterprise, "
            "expert en conception d'architectures scalables, code quality et DevOps"
        ),
        "technical_areas": [
            "Architecture logicielle (SOLID, Clean Architecture, Design Patterns)",
            "Tests automatisés (TDD, BDD, couverture de code, mocking)",
            "Bases de données (SQL/NoSQL, indexation, optimisation requêtes, transactions)",
            "Sécurité applicative (OWASP Top 10, injection SQL, authentification/autorisation)",
            "CI/CD & DevOps (Docker, Kubernetes, pipelines, monitoring, alerting)",
            "Code review & qualité (SonarQube, dette technique, refactoring)",
            "API & intégration (REST, GraphQL, gRPC, microservices, messaging)",
        ],
        "scenario_templates": [
            "Un bug critique en production bloque 30% des utilisateurs. Les logs montrent une exception NullPointerException dans le module de paiement. Comment diagnostiquez-vous et résolvez-vous en moins d'une heure ?",
            "Un junior de votre équipe vous soumet un code qui fonctionne mais avec une complexité O(n³) sur un dataset de 100K lignes. Comment abordez-vous la situation sans le démotiver ?",
            "Le Product Owner demande une feature urgente pour vendredi. L'implémenter correctement nécessite de modifier l'architecture de données. Que faites-vous ?",
            "Votre pipeline CI/CD échoue systématiquement sur les tests d'intégration depuis un déploiement. Vous avez 2h avant la présentation client. Stratégie ?",
        ],
        "green_flag_keywords": [
            "complexité algorithmique", "SOLID", "injection de dépendances",
            "TDD", "tests d'intégration", "tests unitaires", "mocking",
            "SonarQube", "dette technique", "refactoring", "code review",
            "microservices", "event-driven", "idempotent", "rollback",
            "index", "query plan", "EXPLAIN", "cache", "race condition",
            "OWASP", "JWT", "OAuth2", "principe du moindre privilège",
        ],
        "red_flags": [
            "Ne peut pas expliquer un design pattern listé sur son CV",
            "N'a jamais écrit de test automatisé sur ses projets",
            "Confond authentification et autorisation",
            "Ne sait pas ce qu'est un index de base de données",
            "Ne peut pas expliquer la différence entre SQL et NoSQL",
            "Répond à une question de sécurité par 'ça dépend du client'",
        ],
        "evaluation_focus": (
            "Profondeur technique (démontrée, pas récitée) + "
            "résolution de problèmes sous contrainte + "
            "qualité du code et culture DevOps"
        ),
        "phase3_scenario_focus": "débogage production, gestion de la dette technique, arbitrages architecture",
        "phase4_softskill_focus": "rigueur, curiosité technique, collaboration avec des non-techniques",
    },

    # ══════════════════════════════════════════════════════
    # DATA / IA / MACHINE LEARNING
    # ══════════════════════════════════════════════════════
    "Data / IA": {
        "expert_persona": (
            "Lead Data Scientist avec 15 ans d'expérience en ML appliqué, MLOps et statistiques, "
            "ayant déployé des modèles en production dans les secteurs bancaire et industriel"
        ),
        "technical_areas": [
            "Machine Learning supervisé (régression, classification, arbres, ensembles)",
            "Machine Learning non supervisé (clustering, réduction de dimension, anomaly detection)",
            "Feature engineering (normalisation, encoding, imputation, sélection de variables)",
            "Évaluation de modèles (overfitting, cross-validation, métriques adaptées au problème)",
            "MLOps (versioning, déploiement, monitoring drift, réentraînement automatique)",
            "NLP et LLM (embeddings, fine-tuning, RAG, évaluation de modèles de langage)",
            "Visualisation et communication des données (Matplotlib, Seaborn, Tableau, storytelling)",
        ],
        "scenario_templates": [
            "Votre modèle de fraude bancaire a 99% d'accuracy en test mais détecte seulement 30% des fraudes réelles en production. Qu'est-ce qui s'est passé et comment corrigez-vous ?",
            "Un directeur métier dit 'faites-moi un modèle d'IA pour prédire les churns'. Vous n'avez accès qu'à 6 mois de données avec 5% de churns. Comment cadrez-vous le projet ?",
            "Votre dataset a 40% de valeurs manquantes sur la feature la plus prédictive. Décrivez votre stratégie complète de traitement.",
            "Le modèle en production se dégrade progressivement depuis 3 mois. Les données d'entrée semblent correctes. Diagnostic ?",
        ],
        "green_flag_keywords": [
            "data leakage", "class imbalance", "SMOTE", "class weight",
            "cross-validation stratifiée", "AUC-ROC", "précision/rappel",
            "F1-score", "courbe ROC", "matrice de confusion",
            "feature importance", "SHAP", "LIME", "explainabilité",
            "concept drift", "data drift", "pipeline sklearn", "MLflow",
            "reproducibilité", "baseline model", "test A/B",
            "normalisation vs standardisation", "multicolinéarité",
        ],
        "red_flags": [
            "Optimise l'accuracy sans mentionner le déséquilibre de classes",
            "Ne sait pas ce qu'est l'overfitting ou underfitting",
            "N'a pas de baseline de comparaison pour ses modèles",
            "Confond corrélation et causalité",
            "Ne peut pas expliquer comment valider un modèle sans dataset de test",
            "Ignore les questions de déploiement et monitoring post-mise en production",
        ],
        "evaluation_focus": (
            "Rigueur scientifique (méthode, not juste des outils) + "
            "sens du problème métier + "
            "expérience MLOps et contraintes de production"
        ),
        "phase3_scenario_focus": "problèmes de données réelles, déploiement, communication aux non-data",
        "phase4_softskill_focus": "curiosité, rigueur, vulgarisation, autonomie face à l'incertitude",
    },

    # ══════════════════════════════════════════════════════
    # CYBERSÉCURITÉ
    # ══════════════════════════════════════════════════════
    "Cybersécurité": {
        "expert_persona": (
            "CISO expérimenté avec 18 ans en sécurité offensive et défensive, "
            "certifié CISSP et CEH, expert en réponse aux incidents et architecture Zero Trust"
        ),
        "technical_areas": [
            "Sécurité offensive (pentest, OWASP, exploitation de vulnérabilités, CTF)",
            "Sécurité défensive (SIEM, SOC, détection d'intrusion, Blue Team)",
            "Cryptographie (PKI, chiffrement symétrique/asymétrique, TLS, certificats)",
            "Sécurité réseau (firewalls, VPN, segmentation, protocoles, 802.1X)",
            "Gestion des vulnérabilités (CVE, CVSS, patch management, Nessus, OpenVAS)",
            "Conformité & gouvernance (ISO 27001, RGPD, PCI-DSS, NIS2)",
            "Réponse aux incidents (forensics, playbooks, MITRE ATT&CK, containment)",
        ],
        "scenario_templates": [
            "Le SOC vous alerte : trafic inhabituellement élevé vers une adresse IP externe à 3h du matin. Vos étapes de réponse à incident dans les 60 premières minutes ?",
            "Un développeur a poussé par erreur des credentials AWS dans un repo GitHub public il y a 2 heures. Impact et actions immédiates ?",
            "Vous devez convaincre la direction d'investir 200K€ dans une solution SIEM. Comment structurez-vous votre argumentaire en termes de ROI et risque ?",
            "Lors d'un pentest, vous découvrez une injection SQL critique sur l'application en production du client. Que faites-vous maintenant ?",
        ],
        "green_flag_keywords": [
            "MITRE ATT&CK", "IOC", "TTPs", "CVE", "CVSS", "Zero Trust",
            "principe du moindre privilège", "défense en profondeur",
            "WAF", "IDS/IPS", "SIEM", "EDR", "XDR", "SOC",
            "threat hunting", "forensics", "chain of custody",
            "TLS 1.3", "PKI", "certificats", "HSTS", "CSP",
            "OWASP Top 10", "SQL injection", "XSS", "CSRF",
        ],
        "red_flags": [
            "Confond chiffrement et encodage",
            "Ne sait pas ce qu'est une CVE ou un score CVSS",
            "N'a pas de processus de réponse aux incidents structuré",
            "Ne mentionne pas la documentation lors d'un incident",
            "Pense que le VPN suffit à sécuriser un réseau d'entreprise",
        ],
        "evaluation_focus": (
            "Mindset attaquant/défenseur + "
            "réactivité sous pression + "
            "rigueur dans la documentation et la conformité"
        ),
        "phase3_scenario_focus": "gestion d'incident, analyse forensique, communication de crise",
        "phase4_softskill_focus": "sang-froid, éthique, veille permanente, pédagogie",
    },

    # ══════════════════════════════════════════════════════
    # FINANCE / COMPTABILITÉ
    # ══════════════════════════════════════════════════════
    "Finance / Comptabilité": {
        "expert_persona": (
            "Directeur Financier avec 20 ans en audit Big 4, contrôle de gestion et M&A, "
            "expert normes IFRS et accompagnement de dirigeants dans la prise de décision"
        ),
        "technical_areas": [
            "États financiers (bilan, compte de résultat, tableau des flux de trésorerie)",
            "Normes comptables (IFRS, PCG, SYSCOHADA pour l'Afrique, normes tunisiennes)",
            "Analyse financière (ratios de liquidité, solvabilité, rentabilité, valorisation DCF)",
            "Contrôle de gestion (budget, forecast, variance analysis, tableaux de bord KPIs)",
            "Fiscalité (IS, TVA, retenues à la source, conventions fiscales, optimisation légale)",
            "Consolidation et reporting groupe (éliminations intra-groupe, écarts d'acquisition)",
            "Outils (Excel avancé + VBA, SAP FI/CO, Power BI, ERP Sage/Oracle)",
        ],
        "scenario_templates": [
            "Lors de la clôture trimestrielle, vous détectez un écart inexpliqué de 150 KDT entre la comptabilité générale et la comptabilité analytique sur le compte charges de personnel. Procédure ?",
            "La direction vous demande un prévisionnel de trésorerie sur 12 mois d'ici vendredi. Vous n'avez pas accès aux budgets des filiales. Comment procédez-vous ?",
            "Un audit révèle que des provisions pour risques n'ont pas été constituées sur deux exercices consécutifs. Impact sur les états financiers et plan d'action ?",
            "Le CFO vous demande de présenter en 10 minutes l'analyse des écarts budgétaires du semestre devant le Conseil d'Administration. Comment structurez-vous ?",
        ],
        "green_flag_keywords": [
            "EBITDA", "résultat net", "BFR", "cash flow libre", "FCF",
            "amortissement", "provisions", "lettrage", "rapprochement bancaire",
            "variance favorable/défavorable", "cut-off", "principe de prudence",
            "juste valeur", "consolidation", "goodwill", "impôt différé",
            "WAP", "FIFO", "LIFO", "coût de revient", "marge sur coûts variables",
            "seuil de rentabilité", "effet de levier", "ratio d'endettement",
        ],
        "red_flags": [
            "Confond bénéfice comptable et trésorerie disponible",
            "Ne sait pas calculer le BFR ou le cash flow d'exploitation",
            "Ne connaît pas la différence entre normes IFRS et PCG",
            "N'a jamais participé à une clôture mensuelle ou annuelle",
            "Ne peut pas lire un bilan et interpréter la structure financière",
        ],
        "evaluation_focus": (
            "Précision technique et réglementaire + "
            "rigueur sous pression de délai + "
            "capacité à communiquer des chiffres à des non-financiers"
        ),
        "phase3_scenario_focus": "clôture sous pression, anomalies détectées, communication direction",
        "phase4_softskill_focus": "rigueur, intégrité, gestion du stress en période de clôture, discrétion",
    },

    # ══════════════════════════════════════════════════════
    # RESSOURCES HUMAINES
    # ══════════════════════════════════════════════════════
    "Ressources Humaines": {
        "expert_persona": (
            "Directrice des Ressources Humaines avec 18 ans d'expérience en DRH généraliste, "
            "experte droit du travail tunisien et international, développement organisationnel"
        ),
        "technical_areas": [
            "Recrutement & sourcing (entretiens structurés, assessment, marque employeur)",
            "Droit du travail (contrats, licenciement, disciplinaire, RGPD RH, CSP)",
            "Administration du personnel (paie, déclarations sociales, CNSS, SIRH)",
            "Formation & développement (GPEC, plan de formation, bilan de compétences)",
            "Relations sociales (IRP, négociation collective, gestion des conflits)",
            "Performance management (entretiens annuels, KPIs RH, 360°, succession planning)",
            "Culture & engagement (bien-être au travail, onboarding, offboarding, NPS employé)",
        ],
        "scenario_templates": [
            "Un manager vous signale qu'un collaborateur refuse catégoriquement de travailler avec un collègue depuis 3 semaines, sans raison officielle. Comment gérez-vous cette situation d'un point de vue légal et humain ?",
            "Le budget formation est réduit de 50% en urgence. Vous avez 150 collaborateurs et 40 formations planifiées sur l'année. Comment priorisez-vous et communiquez-vous ?",
            "Un candidat que vous avez sélectionné après 3 entretiens accepte l'offre par email puis disparaît 48h avant sa prise de poste. Procédure RH et légale ?",
            "Un directeur métier vous demande de 'se débarrasser discrètement' d'un collaborateur qui dérange. Comment répondez-vous et que faites-vous ?",
        ],
        "green_flag_keywords": [
            "GPEC", "SIRH", "onboarding structuré", "offboarding", "droit du travail",
            "rupture conventionnelle", "période d'essai", "clause de non-concurrence",
            "plan de succession", "marque employeur", "NPS employé",
            "entretien professionnel", "ATS", "sourcing passif", "LinkedIn Recruiter",
            "CNSS", "bulletin de paie", "convention collective", "IRP", "CSE",
            "biais de recrutement", "grille de compétences", "assessment center",
        ],
        "red_flags": [
            "Ne connaît pas les délais légaux de préavis selon le type de contrat",
            "N'a jamais géré un dossier disciplinaire de A à Z",
            "Pense que le recrutement s'arrête à la sélection du CV",
            "Ignore les obligations légales de la formation professionnelle",
            "Ne sait pas ce qu'est la GPEC ou comment la mettre en œuvre",
            "Ne mentionne jamais l'aspect légal dans les scénarios RH",
        ],
        "evaluation_focus": (
            "Maîtrise du cadre légal (non négociable) + "
            "intelligence émotionnelle + "
            "organisation et gestion des priorités en environnement mouvant"
        ),
        "phase3_scenario_focus": "conflits managériaux, contraintes légales, budget limité",
        "phase4_softskill_focus": "écoute active, neutralité, diplomatie, résistance aux pressions hiérarchiques",
    },

    # ══════════════════════════════════════════════════════
    # SANTÉ / MÉDICAL / PARAMÉDICAL
    # ══════════════════════════════════════════════════════
    "Santé / Médical": {
        "expert_persona": (
            "Médecin chef de service avec 22 ans d'expérience clinique et managériale, "
            "expert en gestion des risques hospitaliers et coordination pluridisciplinaire"
        ),
        "technical_areas": [
            "Protocoles cliniques et bonnes pratiques (HAS, OMS, Haute Autorité de Santé)",
            "Gestion des risques et vigilances (pharmacovigilance, identitovigilance, matériovigilance)",
            "Coordination pluridisciplinaire et communication patient/famille",
            "Dossier Patient Informatisé (DPI) et systèmes d'information santé (SIS)",
            "Hygiène et prévention des infections nosocomiales (CPIAS, précautions standard)",
            "Urgences et situations critiques (triage CCMU, gestes d'urgence, SAMU/SMUR)",
            "Éthique médicale (consentement éclairé, secret médical, fin de vie, droits du patient)",
        ],
        "scenario_templates": [
            "Un patient lucide refuse un soin prescrit par le médecin, un soin que vous considérez vital. Comment gérez-vous cette situation sur les plans légal, éthique et pratique ?",
            "Vous constatez qu'un collègue vient d'administrer le mauvais médicament à un patient. Le patient n'a pas encore eu de réaction visible. Procédure exacte dans les 10 prochaines minutes ?",
            "Pic d'activité exceptionnel : 4 soignants absents non remplacés, urgences en flux tendu. Comment organisez-vous l'équipe pour garantir la sécurité des patients ?",
            "Un proche d'un patient vous demande des informations sur son état de santé sans que le patient soit présent ni n'ait donné d'autorisation. Comment répondez-vous ?",
        ],
        "green_flag_keywords": [
            "protocole", "traçabilité", "identitovigilance", "circuit du médicament",
            "prescription médicale", "administration sécurisée", "5 B (bon patient, bon médicament...)",
            "score de Glasgow", "saturation SpO2", "sepsis", "score de douleur EVA",
            "triage CCMU", "gestes d'urgence", "défibrillateur", "RCP",
            "bientraitance", "soins palliatifs", "consentement éclairé",
            "secret médical", "dossier patient", "continuité des soins",
        ],
        "red_flags": [
            "Ne cite pas le protocole d'identitovigilance pour la gestion des médicaments",
            "Réponse floue ou incomplète sur la procédure d'erreur médicamenteuse",
            "Ne mentionne jamais le patient comme acteur central et décisionnaire de ses soins",
            "Ignore les obligations légales de traçabilité et de déclaration d'incidents",
            "Sous-estime ou banalise une situation d'urgence",
        ],
        "evaluation_focus": (
            "Rigueur protocolaire (non négociable en santé) + "
            "gestion du stress en situation critique + "
            "éthique centrée patient + "
            "communication avec équipe pluridisciplinaire"
        ),
        "phase3_scenario_focus": "erreur médicale, urgence organisationnelle, conflit éthique",
        "phase4_softskill_focus": "calme sous pression, empathie sans fusion, esprit d'équipe, signalement",
    },

    # ══════════════════════════════════════════════════════
    # JURIDIQUE / DROIT
    # ══════════════════════════════════════════════════════
    "Juridique / Droit": {
        "expert_persona": (
            "Avocat d'affaires associé avec 20 ans d'expérience en droit des sociétés, "
            "droit des contrats et contentieux commercial, habitué aux dossiers complexes M&A"
        ),
        "technical_areas": [
            "Droit des contrats (rédaction, négociation, clauses sensibles, inexécution)",
            "Droit des sociétés (gouvernance, SARL/SA/SAS, fusions-acquisitions, due diligence)",
            "Contentieux et gestion des litiges (procédures civiles, arbitrage, délais, stratégie)",
            "Conformité & compliance (RGPD, LCB-FT, droit de la concurrence, réglementation sectorielle)",
            "Propriété intellectuelle (brevets, marques, droits d'auteur, licences)",
            "Droit du travail (ruptures, contentieux prud'homal, négociation collective)",
            "Recherche juridique et veille réglementaire (Légifrance, doctrine, jurisprudence)",
        ],
        "scenario_templates": [
            "Un client vous apporte un contrat de prestation à signer dans 2 heures. Vous identifiez une clause limitative de responsabilité qui vous semble abusive. Comment procédez-vous avec le client et avec la partie adverse ?",
            "Deux associés d'une SARL que vous conseillez ont un désaccord fondamental sur la stratégie. L'un veut racheter les parts de l'autre. Quelle est votre analyse juridique et votre rôle dans ce dossier ?",
            "Un partenaire commercial accuse votre client de violation d'une clause de non-concurrence et menace d'une injonction d'urgence. Vous avez 48h. Stratégie de défense ?",
            "Lors d'une due diligence pour un rachat d'entreprise, vous découvrez un contentieux fiscal non provisionné de 500K€. Comment gérez-vous cette information pour votre client acquéreur ?",
        ],
        "green_flag_keywords": [
            "force majeure", "clause résolutoire", "préjudice direct/indirect",
            "prescription extinctive", "jurisprudence", "référé", "injonction",
            "nullité relative/absolue", "dol", "vice du consentement",
            "due diligence", "garantie d'actif et passif", "pacte d'associés",
            "clause de non-concurrence", "confidentialité", "propriété intellectuelle",
            "RGPD", "DPO", "délégation de pouvoir", "responsabilité civile/pénale",
        ],
        "red_flags": [
            "Répond sans citer de fondement juridique (article de loi, jurisprudence)",
            "Ne sait pas ce qu'est la prescription ou ne distingue pas les délais",
            "Confond droit pénal et droit civil dans ses analyses",
            "N'a jamais rédigé ni négocié une clause contractuelle",
            "Donne un avis définitif sans mentionner les risques et alternatives",
        ],
        "evaluation_focus": (
            "Raisonnement juridique structuré (faits → qualification → règle → solution) + "
            "précision des références légales et jurisprudentielles + "
            "conseil stratégique orienté client"
        ),
        "phase3_scenario_focus": "conflit contractuel, urgence procédurale, conseil en situation de crise",
        "phase4_softskill_focus": "rigueur rédactionnelle, diplomatie, résistance aux demandes contraires à l'éthique",
    },

    # ══════════════════════════════════════════════════════
    # INFRASTRUCTURE / DEVOPS / CLOUD
    # ══════════════════════════════════════════════════════
    "Infrastructure / DevOps": {
        "expert_persona": (
            "Architecte Cloud et DevOps avec 16 ans d'expérience, "
            "expert AWS/Azure/GCP certifié, spécialiste haute disponibilité et SRE"
        ),
        "technical_areas": [
            "Cloud (AWS/Azure/GCP : compute, storage, réseau, IAM, facturation)",
            "Conteneurisation & orchestration (Docker, Kubernetes, Helm, service mesh)",
            "Infrastructure as Code (Terraform, Ansible, CloudFormation, Pulumi)",
            "CI/CD avancé (GitOps, ArgoCD, Jenkins, GitHub Actions, pipelines multi-env)",
            "Monitoring & observabilité (Prometheus, Grafana, ELK Stack, tracing distribué)",
            "Sécurité cloud (Zero Trust, secrets management, compliance CIS Benchmark)",
            "SRE & fiabilité (SLI/SLO/SLA, incident management, post-mortem blameless)",
        ],
        "scenario_templates": [
            "Un cluster Kubernetes en production perd 40% de ses nœuds simultanément. Les Pods critiques ne peuvent pas être replanifiés. Vos actions dans les 15 premières minutes ?",
            "La facture AWS du mois dernier est 3x supérieure au budget prévu. Vous n'avez aucune alerte configurée. Comment diagnostiquez-vous et que mettez-vous en place immédiatement ?",
            "On vous demande de migrer une application monolithique critique vers des microservices sur Kubernetes en 6 mois sans interruption de service. Comment planifiez-vous ?",
            "Votre pipeline CI/CD déploie du code défectueux en production. Les tests ont passé. Rollback ou fix-forward ? Justifiez votre choix.",
        ],
        "green_flag_keywords": [
            "haute disponibilité", "fault tolerance", "SLI/SLO/SLA",
            "blue/green deployment", "canary release", "feature flags",
            "observabilité", "distributed tracing", "cardinality",
            "Kubernetes", "Pod disruption budget", "resource limits/requests",
            "Terraform state", "idempotence", "drift detection",
            "secrets manager", "RBAC", "network policy", "service mesh Istio",
        ],
        "red_flags": [
            "Ne sait pas expliquer la différence entre haute disponibilité et tolérance aux pannes",
            "N'a jamais participé à un post-mortem ou à une analyse d'incident",
            "Confond monitoring et observabilité",
            "N'a jamais réfléchi aux coûts cloud dans ses conceptions",
            "Ne peut pas expliquer comment fonctionne Kubernetes scheduling",
        ],
        "evaluation_focus": (
            "Fiabilité et culture SRE + "
            "maîtrise des outils cloud + "
            "réflexe sécurité et coût dans les décisions d'infrastructure"
        ),
        "phase3_scenario_focus": "incident production, migration complexe, optimisation coût/performance",
        "phase4_softskill_focus": "sang-froid en incident, documentation blameless, collaboration Dev+Ops",
    },
}


def get_profile(domaine_metier: str) -> dict:
    """
    Retourne le profil du domaine. Fallback sur IT si domaine inconnu.

    Args:
        domaine_metier: valeur de JobOffer.domaine_metier

    Returns:
        dict profil du domaine
    """
    if domaine_metier in DOMAIN_PROFILES:
        return DOMAIN_PROFILES[domaine_metier]

    # Correspondance partielle (ex: "IT / Dev" → "IT / Développement")
    domaine_lower = (domaine_metier or "").lower()
    for key in DOMAIN_PROFILES:
        if any(word in domaine_lower for word in key.lower().split("/")):
            return DOMAIN_PROFILES[key]

    # Fallback IT
    return DOMAIN_PROFILES["IT / Développement"]


# Mapping des domaines disponibles (pour le frontend OfferNew.jsx)
AVAILABLE_DOMAINS = list(DOMAIN_PROFILES.keys())
