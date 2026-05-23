"""Punto de entrada: `python -m transcriptor`."""

from __future__ import annotations

import sys

from transcriptor.app import main


if __name__ == "__main__":
    sys.exit(main())
