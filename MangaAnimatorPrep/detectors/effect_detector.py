"""Speed-line, impact, energy, and motion-effect detection."""

from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import BoundingBox, Detection
from MangaAnimatorPrep.utils.image_utils import mask_to_bbox, preprocess_manga


class EffectDetector:
    """Detect line-heavy manga effects as separate layers."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, panel: np.ndarray) -> list[Detection]:
        height, width = panel.shape[:2]
        pre = preprocess_manga(panel, self.config.preprocessing)
        edges = pre["edges"]
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=max(20, min(width, height) // 8), maxLineGap=8)
        mask = np.zeros((height, width), dtype=np.uint8)
        line_count = 0
        if lines is not None:
            for line in lines[:, 0, :]:
                x1, y1, x2, y2 = [int(value) for value in line]
                length = float(np.hypot(x2 - x1, y2 - y1))
                if length < max(16, min(width, height) * 0.08):
                    continue
                cv2.line(mask, (x1, y1), (x2, y2), 255, 2)
                line_count += 1
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
        if line_count == 0 or cv2.countNonZero(mask) < width * height * 0.002:
            return []
        bbox = mask_to_bbox(mask).clamp(width, height)
        confidence = min(0.90, 0.20 + line_count / 80.0)
        label = "speed_lines" if line_count >= 8 else "motion_effect"
        return [Detection("effect", bbox, confidence, mask=mask, label=label)]

