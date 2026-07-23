from pathlib import Path
import sys

EXPERIMENT_ROOT = Path(__file__).resolve().parent
MOTIF_ROOT = EXPERIMENT_ROOT.parent / "pixie_etale_motif_search_v0_1"
for path in (EXPERIMENT_ROOT, MOTIF_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pixie_lora_feedback.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
