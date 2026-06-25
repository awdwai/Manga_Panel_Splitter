"""Manga panel detection using contour and border heuristics."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import BoundingBox, Detection
from MangaAnimatorPrep.utils.image_utils import preprocess_manga

LOGGER = logging.getLogger(__name__)


class PanelDetector:
    """Detect rectangular, irregular, overlapping, and borderless manga panels."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, image: np.ndarray) -> list[Detection]:
        height, width = image.shape[:2]
        min_area = int(width * height * self.config.min_panel_area_ratio)
        pre = preprocess_manga(image, self.config.preprocessing)

        candidates = self._contour_candidates(pre["edges"], width, height, min_area)
        candidates.extend(self._white_region_candidates(pre["threshold"], width, height, min_area))
        detections = self._deduplicate(candidates, width, height)
        detections = self._drop_outer_page(detections, width, height)

        if not detections:
            LOGGER.info("No panel candidates found; treating input as one panel")
            mask = np.full((height, width), 255, dtype=np.uint8)
            detections = [Detection("panel", BoundingBox(0, 0, width, height), 1.0, mask=mask, label="panel")]

        return sorted(detections, key=lambda det: (det.bbox.y // max(1, height // 10), det.bbox.x))

    def _contour_candidates(self, edges: np.ndarray, width: int, height: int, min_area: int) -> list[Detection]:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h).clamp(width, height)
            if not self._valid_panel_bbox(bbox, width, height, min_area):
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
            contour_area = max(1.0, float(cv2.contourArea(contour)))
            rectangularity = min(1.0, contour_area / max(1.0, float(bbox.area)))
            confidence = 0.55 + 0.4 * rectangularity
            detections.append(Detection("panel", bbox, confidence, mask=mask, label="panel", contour=contour))
        return detections

    def _white_region_candidates(self, threshold: np.ndarray, width: int, height: int, min_area: int) -> list[Detection]:
        """Detect borderless panels as large light regions bounded by page art/gutters."""

        light = cv2.threshold(threshold, 245, 255, cv2.THRESH_BINARY)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        opened = cv2.morphologyEx(light, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h).clamp(width, height)
            if not self._valid_panel_bbox(bbox, width, height, min_area):
                continue
            if bbox.area > 0.92 * width * height:
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
            detections.append(Detection("panel", bbox, 0.45, mask=mask, label="borderless_panel", contour=contour))
        return detections

    def _valid_panel_bbox(self, bbox: BoundingBox, width: int, height: int, min_area: int) -> bool:
        if bbox.area < min_area:
            return False
        if bbox.width < max(20, width * 0.05) or bbox.height < max(20, height * 0.05):
            return False
        if bbox.width > 0.99 * width and bbox.height > 0.99 * height:
            return True
        return True

    def _deduplicate(self, detections: list[Detection], width: int, height: int) -> list[Detection]:
        detections = sorted(detections, key=lambda det: det.confidence, reverse=True)
        kept: list[Detection] = []
        for detection in detections:
            if any(self._iou(detection.bbox, existing.bbox) > 0.70 for existing in kept):
                continue
            kept.append(detection)
        return [Detection(det.kind, det.bbox.clamp(width, height), det.confidence, det.mask, det.label, det.contour, det.metadata) for det in kept]

    def _drop_outer_page(self, detections: list[Detection], width: int, height: int) -> list[Detection]:
        if len(detections) <= 1:
            return detections
        page_area = width * height
        filtered = [det for det in detections if det.bbox.area < 0.90 * page_area]
        return filtered or detections

    @staticmethod
    def _iou(a: BoundingBox, b: BoundingBox) -> float:
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x2, b.x2)
        y2 = min(a.y2, b.y2)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = a.area + b.area - inter
        return inter / union if union else 0.0

