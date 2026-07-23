from pathlib import Path
import sys


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
MOTIF_ROOT = EXPERIMENT_ROOT.parent / "pixie_etale_motif_search_v0_1"
for path in (EXPERIMENT_ROOT, MOTIF_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
