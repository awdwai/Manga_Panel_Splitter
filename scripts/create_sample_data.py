"""Create deterministic synthetic manga-like sample images for smoke tests."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def create_sample(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = np.full((720, 520, 3), 255, dtype=np.uint8)
    panels = [(30, 30, 230, 300), (270, 30, 490, 300), (30, 340, 490, 690)]
    for x1, y1, x2, y2 in panels:
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 0), 4)
    # Character silhouettes.
    cv2.circle(canvas, (130, 120), 32, (20, 20, 20), -1)
    cv2.ellipse(canvas, (130, 210), (45, 75), 0, 0, 360, (35, 35, 35), -1)
    cv2.line(canvas, (92, 200), (65, 260), (35, 35, 35), 8)
    cv2.line(canvas, (168, 200), (200, 260), (35, 35, 35), 8)
    cv2.circle(canvas, (380, 125), 36, (20, 20, 20), -1)
    cv2.ellipse(canvas, (380, 220), (55, 80), 0, 0, 360, (35, 35, 35), -1)
    cv2.circle(canvas, (245, 465), 42, (20, 20, 20), -1)
    cv2.ellipse(canvas, (245, 580), (70, 90), 0, 0, 360, (35, 35, 35), -1)
    # Speech bubbles and text.
    cv2.ellipse(canvas, (170, 75), (45, 26), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(canvas, (170, 75), (45, 26), 0, 0, 360, (0, 0, 0), 2)
    cv2.putText(canvas, "HI", (154, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.rectangle(canvas, (330, 55), (455, 100), (255, 255, 255), -1)
    cv2.rectangle(canvas, (330, 55), (455, 100), (0, 0, 0), 2)
    cv2.putText(canvas, "BOOM", (345, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    # Speed lines.
    for offset in range(0, 180, 20):
        cv2.line(canvas, (335 + offset // 2, 350), (455, 520 + offset // 3), (0, 0, 0), 2)
    Image.fromarray(canvas).save(path)


def main() -> int:
    create_sample(Path("sample_data/sample_page.png"))
    print("Created sample_data/sample_page.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

