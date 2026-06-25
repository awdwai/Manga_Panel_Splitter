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
        detections: list[Detection] = []

        # White interiors can merge with the page background for borderless/cropped panels,
        # so detect dark closed outlines first and then fill them as bubble masks.
        dark = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)[1]
        dark = self._remove_border_connected(dark)
        outlined = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=2)
        outline_contours, _ = cv2.findContours(outlined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in outline_contours:
            detection = self._candidate_from_contour(contour, width, height)
            if detection is not None:
                detections.append(detection)

        light = cv2.inRange(gray, 235, 255)
        light = cv2.morphologyEx(light, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)), iterations=2)
        contours, _ = cv2.findContours(light, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            detection = self._candidate_from_contour(contour, width, height)
            if detection is not None and not any(self._iou(detection.bbox, existing.bbox) > 0.5 for existing in detections):
                detections.append(detection)
        return sorted(detections, key=lambda det: (det.bbox.y, det.bbox.x))

    def _candidate_from_contour(self, contour: np.ndarray, width: int, height: int) -> Detection | None:
        x, y, w, h = cv2.boundingRect(contour)
        bbox = BoundingBox(x, y, w, h).clamp(width, height)
        area_ratio = bbox.area / max(1, width * height)
        if area_ratio < 0.01 or area_ratio > 0.45:
            return None
        if bbox.width < 20 or bbox.height < 15:
            return None
        contour_area = cv2.contourArea(contour)
        rectangularity = contour_area / max(1, bbox.area)
        aspect = bbox.width / max(1, bbox.height)
        if rectangularity < 0.20 or not (0.25 < aspect < 5.0):
            return None
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
        label = "narration_box" if rectangularity > 0.82 and (bbox.width > 1.3 * bbox.height) else "speech"
        confidence = min(0.90, 0.35 + rectangularity * 0.50)
        return Detection("speech", bbox, confidence, mask=mask, label=label, contour=contour)

    @staticmethod
    def _iou(a: BoundingBox, b: BoundingBox) -> float:
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x2, b.x2)
        y2 = min(a.y2, b.y2)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = a.area + b.area - inter
        return inter / union if union else 0.0

    @staticmethod
    def _remove_border_connected(mask: np.ndarray) -> np.ndarray:
        """Remove panel frames and other ink connected to the crop border."""

        cleaned = mask.copy()
        count, labels, _, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if count <= 1:
            return cleaned
        border_labels = set(np.unique(labels[0, :]))
        border_labels.update(np.unique(labels[-1, :]))
        border_labels.update(np.unique(labels[:, 0]))
        border_labels.update(np.unique(labels[:, -1]))
        for label in border_labels:
            if label != 0:
                cleaned[labels == label] = 0
        return cleaned

