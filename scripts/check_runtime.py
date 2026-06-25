"""Verify MangaAnimatorPrep runtime dependencies without shell quoting hazards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REQUIRED_MODULES = [
    "cv2",
    "numpy",
    "PIL",
    "pydantic",
    "rich",
    "PySide6",
    "tqdm",
    "psutil",
    "onnxruntime",
    "torch",
    "torchvision",
    "MangaAnimatorPrep",
]


def main() -> int:
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        print("Missing required Python modules: " + ", ".join(missing))
        return 1
    print("Required runtime dependencies found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

