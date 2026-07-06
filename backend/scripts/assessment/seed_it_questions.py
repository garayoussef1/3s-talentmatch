"""
Seed d'une banque de questions IT pour le module "Reality Gap Score".

- QCM (assessment_questions) : Python / SQL / JavaScript, difficulté 1-10.
  La difficulté alimente le paramètre IRT `b` ; `discrimination` = paramètre `a`.
- Questions ouvertes (open_questions) : 3 réponses de référence
  (experte / correcte / faible). Les embeddings BGE-M3 sont calculés
  séparément (Phase 2 : scripts.assessment.compute_embeddings).

Idempotent : ne réinsère pas si le domaine "IT" est déjà seedé.
Usage (depuis backend/) : python -m scripts.assessment.seed_it_questions
"""
from app.database import SessionLocal
from app.models.assessment import AssessmentQuestion, OpenQuestion


# ── QCM : (competence, difficulte 1-10, discrimination, question, options, index_bonne_reponse) ──
QCM = [
    # ---- Python ----
    ("Python", 1, 1.0, "Quel mot-clé définit une fonction en Python ?",
     ["func", "def", "function", "lambda"], 1),
    ("Python", 2, 1.0, "Quelle structure est immuable en Python ?",
     ["list", "dict", "set", "tuple"], 3),
    ("Python", 3, 1.1, "Que renvoie len('abc') ?",
     ["2", "3", "4", "Erreur"], 1),
    ("Python", 4, 1.2, "Quel est le résultat de [1,2,3][::-1] ?",
     ["[1,2,3]", "[3,2,1]", "[3,2]", "Erreur"], 1),
    ("Python", 5, 1.2, "À quoi sert `if __name__ == '__main__':` ?",
     ["Déclarer une classe", "Exécuter le code seulement si le fichier est lancé directement",
      "Importer un module", "Définir le point d'entrée obligatoire"], 1),
    ("Python", 6, 1.3, "Que fait une list comprehension `[x*2 for x in range(3)]` ?",
     ["[0,1,2]", "[0,2,4]", "[2,4,6]", "Erreur"], 1),
    ("Python", 7, 1.3, "Quelle est la différence entre `is` et `==` ?",
     ["Aucune", "`is` compare l'identité (adresse), `==` compare les valeurs",
      "`==` compare l'identité", "`is` ne marche que sur les nombres"], 1),
    ("Python", 8, 1.4, "Que renvoie un générateur (`yield`) ?",
     ["Une liste", "Un itérateur paresseux (lazy)", "Un dictionnaire", "Une coroutine async"], 1),
    ("Python", 9, 1.4, "Que garantit un context manager (`with`) ?",
     ["La rapidité", "La libération des ressources même en cas d'exception",
      "Le multithreading", "La compilation"], 1),
    ("Python", 10, 1.5, "Que fait le GIL (Global Interpreter Lock) en CPython ?",
     ["Accélère le calcul", "Empêche l'exécution simultanée de bytecode Python par plusieurs threads",
      "Gère la mémoire GPU", "Compile le code en C"], 1),

    # ---- SQL ----
    ("SQL", 2, 1.0, "Quelle clause filtre les lignes d'une requête ?",
     ["ORDER BY", "WHERE", "GROUP BY", "HAVING"], 1),
    ("SQL", 3, 1.1, "Quel mot-clé supprime les doublons dans un SELECT ?",
     ["UNIQUE", "DISTINCT", "DEDUP", "ONLY"], 1),
    ("SQL", 5, 1.2, "Quelle jointure garde toutes les lignes de la table de gauche ?",
     ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"], 1),
    ("SQL", 6, 1.3, "À quoi sert GROUP BY ?",
     ["Trier", "Agréger les lignes par valeur d'une colonne", "Filtrer", "Joindre"], 1),
    ("SQL", 8, 1.4, "Quelle clause filtre APRÈS une agrégation GROUP BY ?",
     ["WHERE", "HAVING", "FILTER", "ON"], 1),
    ("SQL", 9, 1.4, "Qu'est-ce qu'un index améliore principalement ?",
     ["L'écriture", "La vitesse de lecture/recherche", "La sécurité", "La normalisation"], 1),

    # ---- JavaScript ----
    ("JavaScript", 2, 1.0, "Quel mot-clé déclare une variable de portée bloc ?",
     ["var", "let", "const", "let et const"], 3),
    ("JavaScript", 3, 1.1, "Que renvoie typeof null ?",
     ["'null'", "'object'", "'undefined'", "'number'"], 1),
    ("JavaScript", 5, 1.2, "Que fait `===` par rapport à `==` ?",
     ["Rien", "Compare valeur ET type (pas de coercition)", "Compare seulement le type",
      "Compare les adresses"], 1),
    ("JavaScript", 6, 1.3, "Qu'est-ce qu'une Promise ?",
     ["Une boucle", "Un objet représentant une valeur future (asynchrone)",
      "Un type de tableau", "Une fonction pure"], 1),
    ("JavaScript", 8, 1.4, "Que fait `async/await` ?",
     ["Rend le code synchrone", "Écrit du code asynchrone de façon lisible (sur les Promises)",
      "Crée des threads", "Bloque le navigateur"], 1),
    ("JavaScript", 9, 1.4, "Qu'est-ce qu'une closure ?",
     ["Une fermeture de connexion", "Une fonction qui capture les variables de son scope parent",
      "Un objet gelé", "Un module ES6"], 1),
]


# ── Questions ouvertes : (domaine, competence, question, ref_expert, ref_correct, ref_faible) ──
OPEN = [
    ("IT", "Python",
     "Expliquez la différence entre une liste et un tuple en Python, et quand utiliser chacun.",
     "Une liste est mutable (modifiable après création) et un tuple est immuable. "
     "Les listes conviennent aux collections évolutives (ajout/suppression), les tuples "
     "aux données fixes (coordonnées, clés de dictionnaire) ; leur immuabilité les rend "
     "hashables et légèrement plus performants en lecture. On choisit le tuple pour garantir "
     "l'intégrité des données et signaler qu'elles ne doivent pas changer.",
     "Une liste peut être modifiée (append, del) mais pas un tuple. On utilise une liste "
     "quand on veut ajouter ou enlever des éléments, et un tuple quand les données ne changent pas.",
     "La liste utilise des crochets et le tuple des parenthèses."),

    ("IT", "SQL",
     "Qu'est-ce qu'une jointure SQL et quelle est la différence entre INNER JOIN et LEFT JOIN ?",
     "Une jointure combine des lignes de deux tables selon une condition (souvent une clé "
     "étrangère). INNER JOIN ne renvoie que les lignes ayant une correspondance dans les deux "
     "tables. LEFT JOIN renvoie toutes les lignes de la table de gauche, complétées par NULL "
     "quand il n'y a pas de correspondance à droite — utile pour détecter les enregistrements "
     "orphelins ou conserver l'ensemble de référence.",
     "Une jointure relie deux tables. INNER JOIN garde seulement les lignes qui existent dans "
     "les deux tables, LEFT JOIN garde toutes les lignes de gauche même sans correspondance (avec NULL).",
     "INNER JOIN et LEFT JOIN servent à joindre des tables, la différence est le sens."),

    ("IT", "JavaScript",
     "Expliquez ce qu'est une closure en JavaScript avec un cas d'usage concret.",
     "Une closure est une fonction qui conserve l'accès aux variables de sa portée lexicale "
     "parente même après que cette fonction parente a fini de s'exécuter. Cas d'usage : créer "
     "un compteur privé — une fonction externe déclare `let count=0` et renvoie une fonction "
     "interne qui incrémente et renvoie `count` ; l'état est encapsulé et inaccessible de "
     "l'extérieur. Les closures sont au cœur des modules, du currying et des callbacks.",
     "Une closure est une fonction qui garde accès aux variables de la fonction dans laquelle "
     "elle a été créée. Par exemple, une fonction qui renvoie une autre fonction utilisant une "
     "variable locale, comme un compteur.",
     "C'est une fonction dans une fonction."),
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(AssessmentQuestion).filter(AssessmentQuestion.domaine == "IT").count()
        if existing:
            print(f"Domaine IT déjà seedé ({existing} QCM). Rien à faire.")
            return

        for comp, diff, disc, q, opts, ans in QCM:
            db.add(AssessmentQuestion(
                domaine="IT", competence_esco=comp, difficulte=diff,
                discrimination=disc, question=q, options=opts, bonne_reponse=ans,
            ))
        for dom, comp, q, exp, cor, faible in OPEN:
            db.add(OpenQuestion(
                domaine=dom, competence_esco=comp, question=q,
                ref_expert=exp, ref_correct=cor, ref_faible=faible,
            ))
        db.commit()
        print(f"Seed OK : {len(QCM)} QCM + {len(OPEN)} questions ouvertes (domaine IT).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
