#!/usr/bin/env python3
"""Entry point usable from a staged or installed data directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from add_to_applications.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
