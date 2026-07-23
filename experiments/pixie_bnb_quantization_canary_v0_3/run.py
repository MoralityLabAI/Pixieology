from pathlib import Path
import sys


EXPERIMENT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_ROOT))

from pixie_bnb_canary_v3.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
