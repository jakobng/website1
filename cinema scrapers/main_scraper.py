#!/usr/bin/env python3
"""Compatibility wrapper for the revamped cinema scraper suite."""
from __future__ import annotations

import sys

from pathlib import Path

# Ensure the package on the parent directory is importable when the script is
# executed directly from the legacy ``cinema scrapers`` folder.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cinema_scrapers.cli import main


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
