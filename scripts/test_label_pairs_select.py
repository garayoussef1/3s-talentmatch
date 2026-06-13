import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from label_pairs import OFFERS, CANDS, select_pairs
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

scorer = BERTMatchingScorer()
scorer._ensure_loaded()
pairs = select_pairs(scorer)

print(f"Paires selectionnees : {len(pairs)}")
same_dom = sum(1 for p in pairs if p["odom"] == p["cdom"])
diff_dom = len(pairs) - same_dom
print(f"  Meme domaine : {same_dom}")
print(f"  Hors-domaine : {diff_dom}")

low  = sum(1 for p in pairs if p["sem"] < 0.55)
mid  = sum(1 for p in pairs if 0.55 <= p["sem"] <= 0.72)
high = sum(1 for p in pairs if p["sem"] > 0.72)
print(f"  Sem < 0.55  (bas)     : {low}")
print(f"  Sem 0.55-0.72 (moyen) : {mid}")
print(f"  Sem > 0.72  (haut)    : {high}")

print("Exemples (5 premieres paires) :")
for p in pairs[:5]:
    print(f"  [{p['sem']*100:.0f}%] {p['oname']:22s} x {p['cname']:22s} ({p['odom']}→{p['cdom']})")
