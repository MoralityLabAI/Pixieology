from pathlib import Path
import sys

EXPERIMENT_ROOT = Path(__file__).resolve().parent
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from pixie_etale_capture_v2.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
