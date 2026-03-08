"""Test des améliorations ContactExtractor + EntityExtractor."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.nlp.contact_extractor import ContactExtractor
from app.services.nlp.entity_extractor import EntityExtractor
import spacy

nlp = spacy.load("fr_core_news_md")
ce = ContactExtractor()
ee = EntityExtractor(nlp)

# ---------- Test 1 : CV complet ----------
cv1 = """Youssef Gara
Tunis, Tunisie
Email: youssef.gara@esprit.tn
Tel: +216 22 333 444
LinkedIn: linkedin.com/in/youssef-gara
GitHub: github.com/youssefgara
Portfolio: https://youssef.dev

Profil
Ingenieur logiciel avec 3 ans d experience.
"""

print("=" * 50)
print("TEST 1 : CV complet avec tous les contacts")
print("=" * 50)
r1 = ce.extract(cv1)
n1 = ee.extract_full_name(cv1)
print(f"  nom       : {n1}")
print(f"  email     : {r1['primary_email']}")
print(f"  phone     : {r1['primary_phone']}")
print(f"  linkedin  : {r1['linkedin']}")
print(f"  github    : {r1['github']}")
print(f"  website   : {r1['website']}")
print(f"  address   : {r1['address']}")

assert n1 is not None, "FAIL: nom devrait etre Youssef Gara"
assert r1["primary_email"] == "youssef.gara@esprit.tn", f"FAIL email: {r1['primary_email']}"
assert r1["primary_phone"] is not None, f"FAIL phone: {r1['primary_phone']}"
assert r1["linkedin"] is not None, f"FAIL linkedin: {r1['linkedin']}"
assert r1["github"] is not None, f"FAIL github: {r1['github']}"
print("  >>> PASS\n")

# ---------- Test 2 : Nom en MAJUSCULES ----------
cv2 = """AHMED BEN SALAH
ahmed.bensalah@gmail.com
+216 98 765 432
LinkedIn : https://www.linkedin.com/in/ahmed-ben-salah
GitHub : https://github.com/ahmedbs

Developpeur Java Senior
"""

print("=" * 50)
print("TEST 2 : Nom en majuscules + LinkedIn/GitHub URLs")
print("=" * 50)
r2 = ce.extract(cv2)
n2 = ee.extract_full_name(cv2)
print(f"  nom       : {n2}")
print(f"  email     : {r2['primary_email']}")
print(f"  phone     : {r2['primary_phone']}")
print(f"  linkedin  : {r2['linkedin']}")
print(f"  github    : {r2['github']}")

assert n2 is not None, "FAIL: nom devrait etre Ahmed Ben Salah"
assert "Ahmed" in (n2 or ""), f"FAIL: nom {n2} ne contient pas Ahmed"
assert r2["linkedin"] is not None, f"FAIL linkedin: {r2['linkedin']}"
assert r2["github"] is not None, f"FAIL github: {r2['github']}"
print("  >>> PASS\n")

# ---------- Test 3 : Format simple ----------
cv3 = """Marie-Claire Dupont
Ingenieure DevOps
marie.dupont@orange.fr
06 12 34 56 78
github.com/mariedupont

Experience
Senior DevOps chez Orange depuis 2020
"""

print("=" * 50)
print("TEST 3 : Format simple, GitHub sans label")
print("=" * 50)
r3 = ce.extract(cv3)
n3 = ee.extract_full_name(cv3)
print(f"  nom       : {n3}")
print(f"  email     : {r3['primary_email']}")
print(f"  phone     : {r3['primary_phone']}")
print(f"  github    : {r3['github']}")

assert n3 is not None, f"FAIL: nom devrait etre Marie-Claire Dupont, got {n3}"
assert r3["primary_email"] == "marie.dupont@orange.fr"
assert r3["github"] is not None, f"FAIL github: {r3['github']}"
print("  >>> PASS\n")

# ---------- Test 4 : Pas de nom clair ----------
cv4 = """Curriculum Vitae
Email: test@mail.com
Tel: +33 6 11 22 33 44
Competences: Python, Java
"""

print("=" * 50)
print("TEST 4 : CV sans nom clair (doit retourner None)")
print("=" * 50)
n4 = ee.extract_full_name(cv4)
print(f"  nom       : {n4}")
assert n4 is None, f"FAIL: devrait etre None, got {n4}"
print("  >>> PASS\n")

# ---------- Test 5 : prefix Nom: ----------
cv5 = """Nom: Fatma Trabelsi
Email: fatma.trabelsi@yahoo.fr
Telephone: 55 123 456
Adresse: 10 rue de la Liberte, Sousse, Tunisie
LinkedIn: linkedin.com/in/fatma-trabelsi
"""

print("=" * 50)
print("TEST 5 : Nom avec prefix + adresse tunisienne")
print("=" * 50)
r5 = ce.extract(cv5)
n5 = ee.extract_full_name(cv5)
print(f"  nom       : {n5}")
print(f"  email     : {r5['primary_email']}")
print(f"  phone     : {r5['primary_phone']}")
print(f"  linkedin  : {r5['linkedin']}")
print(f"  address   : {r5['address']}")

assert n5 is not None and "Fatma" in n5, f"FAIL nom: {n5}"
assert r5["primary_email"] == "fatma.trabelsi@yahoo.fr"
assert r5["linkedin"] is not None
assert r5["address"] is not None, f"FAIL address: {r5['address']}"
print("  >>> PASS\n")

# ---------- Résumé ----------
print("=" * 50)
print("TOUS LES TESTS PASSES !")
print("=" * 50)
