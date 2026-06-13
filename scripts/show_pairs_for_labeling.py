"""Affiche les 40 paires avec scores complets pour annotation manuelle."""
import sys, os, warnings
warnings.filterwarnings("ignore")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "backend"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from label_pairs import OFFERS, CANDS, select_pairs
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

scorer = BERTMatchingScorer()
scorer._ensure_loaded()
pairs = select_pairs(scorer)

print(f"{'#':3} {'Score':6} {'Offre':28} {'Candidat':24} {'Dom O':8} {'Dom C':10} {'Confiance'}")
print("-" * 100)
for i, p in enumerate(pairs, 1):
    score, details = scorer.score(p["offer"], p["cand"])
    conf = "HAUT" if score > 0.70 else ("BAS" if score < 0.35 else "HESIT")
    print(f"{i:3} {score*100:5.1f}%  {p['offer'].titre[:28]:28} {p['cand'].nom[:24]:24} {p['odom']:8} {p['cdom']:10} {conf}")
