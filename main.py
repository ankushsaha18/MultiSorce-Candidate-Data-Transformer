"""Repository-root CLI shim.

Allows running:

python main.py --csv samples/recruiter_csv/ankush_saha.csv \\
  --resume samples/resume_pdf/ankush_saha.pdf \\
  --config configs/default_projection.json --output outputs/result.json
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from candidate_transformer.app.cli import main


if __name__ == "__main__":
    sys.exit(main())
