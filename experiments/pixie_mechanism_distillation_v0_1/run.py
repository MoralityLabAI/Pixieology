from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pixie_mechanism_distillation.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
