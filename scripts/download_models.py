"""Prepare model cache directories and print verified source hints.

This script intentionally avoids downloading very large checkpoints by default. Many model
licenses and distribution URLs change over time, so production deployments should pin approved
artifacts in the local model cache and set config paths accordingly.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


MODEL_HINTS = {
    "groundingdino": {
        "purpose": "open-vocabulary character detection",
        "source": "https://github.com/IDEA-Research/GroundingDINO",
        "expected_files": ["groundingdino_config.py", "groundingdino_checkpoint.pth"],
    },
    "sam2": {
        "purpose": "character segmentation refinement",
        "source": "https://github.com/facebookresearch/sam2",
        "expected_files": ["sam2_config.yaml", "sam2_checkpoint.pt"],
    },
    "lama": {
        "purpose": "background reconstruction / inpainting",
        "source": "https://github.com/advimman/lama",
        "expected_files": ["lama_checkpoint"],
    },
    "openpose": {
        "purpose": "pose fallback when MediaPipe is insufficient",
        "source": "https://github.com/CMU-Perceptual-Computing-Lab/openpose",
        "expected_files": ["pose_iter_584000.caffemodel", "pose_deploy_linevec.prototxt"],
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create MangaAnimatorPrep model cache directories.")
    parser.add_argument("--models-dir", type=Path, default=Path("MangaAnimatorPrep/models"))
    parser.add_argument("--verify", action="store_true", help="Print SHA256 checksums for files already present.")
    args = parser.parse_args()
    args.models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Model cache: {args.models_dir.resolve()}")
    for name, info in MODEL_HINTS.items():
        model_dir = args.models_dir / name
        model_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n{name}: {info['purpose']}")
        print(f"  source: {info['source']}")
        print("  expected files:")
        for filename in info["expected_files"]:
            path = model_dir / filename
            status = "present" if path.exists() else "missing"
            print(f"    - {filename}: {status}")
            if args.verify and path.is_file():
                print(f"      sha256: {sha256(path)}")
    print("\nSet MANGA_ANIMATOR_MODELS_DIR or config.json model paths after placing checkpoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

