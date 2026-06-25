"""Speech bubble, thought bubble, narration box, and text-box detection."""

from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import BoundingBox, Detection
from MangaAnimatorPrep.utils.image_utils import preprocess_manga


class SpeechDetector:
    """Detect speech/text containers as exportable transparent layers."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, panel: np.ndarray) -> list[Detection]:
        height, width = panel.shape[:2]
        pre = preprocess_manga(panel, self.config.preprocessing)
        gray = pre["gray"]
        light = cv2.inRange(gray, 235, 255)
        light = cv2.morphologyEx(light, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)), iterations=2)
        contours, _ = cv2.findContours(light, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h).clamp(width, height)
            area_ratio = bbox.area / max(1, width * height)
            if area_ratio < 0.01 or area_ratio > 0.45:
                continue
            if bbox.width < 20 or bbox.height < 15:
                continue
            contour_area = cv2.contourArea(contour)
            rectangularity = contour_area / max(1, bbox.area)
            aspect = bbox.width / max(1, bbox.height)
            if rectangularity < 0.45 and not (0.25 < aspect < 4.0):
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
            label = "narration_box" if rectangularity > 0.82 and (bbox.width > 1.3 * bbox.height) else "speech"
            confidence = min(0.90, 0.35 + rectangularity * 0.50)
            detections.append(Detection("speech", bbox, confidence, mask=mask, label=label, contour=contour))
        return sorted(detections, key=lambda det: (det.bbox.y, det.bbox.x))

