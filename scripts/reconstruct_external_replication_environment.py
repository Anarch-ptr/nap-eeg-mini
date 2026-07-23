"""CLI wrapper for the non-scientific Phase II-A reconstruction verifier."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.external_replication.reconstruction import main


if __name__ == "__main__":
    raise SystemExit(main())
