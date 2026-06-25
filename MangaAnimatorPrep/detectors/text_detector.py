"""Text-region detection and mask creation."""

from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import BoundingBox, Detection
from MangaAnimatorPrep.utils.image_utils import preprocess_manga


class TextDetector:
    """Detect manga lettering regions independently of speech bubbles."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, panel: np.ndarray) -> list[Detection]:
        height, width = panel.shape[:2]
        pre = preprocess_manga(panel, self.config.preprocessing)
        dark = cv2.threshold(pre["enhanced"], 90, 255, cv2.THRESH_BINARY_INV)[1]
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3)), iterations=2)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)), iterations=1)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h).pad(2, width, height)
            area_ratio = bbox.area / max(1, width * height)
            if area_ratio < 0.001 or area_ratio > 0.20:
                continue
            if bbox.height > height * 0.35 and bbox.width > width * 0.35:
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
            confidence = min(0.8, 0.30 + area_ratio * 5.0)
            detections.append(Detection("text", bbox, confidence, mask=mask, label="text", contour=contour))
        return sorted(detections, key=lambda det: (det.bbox.y, det.bbox.x))

