"""PyInstaller GUI entrypoint for development executable builds."""

from __future__ import annotations

import sys

from MangaAnimatorPrep.main import main


if __name__ == "__main__":
    sys.exit(main(["gui"]))

