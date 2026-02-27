import sys
from pathlib import Path

# Ajouter backend/ au path Python pour tous les tests
sys.path.insert(0, str(Path(__file__).parent.parent))
