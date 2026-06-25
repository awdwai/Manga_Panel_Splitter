"""Character detection with GroundingDINO-ready lazy backend and CPU fallback."""

from __future__ import annotations

import importlib
import logging

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import BoundingBox, Detection
from MangaAnimatorPrep.utils.image_utils import preprocess_manga
from MangaAnimatorPrep.utils.model_cache import GLOBAL_MODEL_CACHE

LOGGER = logging.getLogger(__name__)


class CharacterDetector:
    """Detect visible manga characters in a panel."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, panel: np.ndarray) -> list[Detection]:
        backend = self._load_grounding_dino_if_configured()
        if backend is not None:
            try:
                return backend.detect(panel)
            except Exception as exc:  # pragma: no cover - optional backend
                LOGGER.warning("GroundingDINO backend failed, using fallback: %s", exc)
        return self._fallback_detect(panel)

    def _load_grounding_dino_if_configured(self) -> object | None:
        if not self.config.models.grounding_dino_checkpoint:
            return None

        def loader() -> object:
            importlib.import_module("torch")
            # GroundingDINO packaging varies by distribution. Keep construction isolated so
            # a production adapter can be dropped in without touching the pipeline.
            module = importlib.import_module("groundingdino.util.inference")
            return GroundingDinoAdapter(module, self.config)

        return GLOBAL_MODEL_CACHE.get_or_load("grounding_dino", loader).value

    def _fallback_detect(self, panel: np.ndarray) -> list[Detection]:
        height, width = panel.shape[:2]
        min_area = int(width * height * self.config.min_character_area_ratio)
        pre = preprocess_manga(panel, self.config.preprocessing)
        dark = cv2.threshold(pre["enhanced"], 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=2)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, w, h).pad(4, width, height)
            if bbox.area < min_area or bbox.height < height * 0.18:
                continue
            if bbox.width > width * 0.96 and bbox.height > height * 0.96:
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
            confidence = min(0.85, 0.35 + bbox.area / max(1.0, width * height))
            detections.append(Detection("character", bbox, confidence, mask=mask, label="character", contour=contour))

        detections = self._merge_overlapping(detections, width, height)
        if detections:
            return detections

        # Fallback for sparse panels: provide a conservative central visible-character region.
        bbox = BoundingBox(width // 4, height // 5, width // 2, int(height * 0.70)).clamp(width, height)
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.ellipse(mask, (bbox.x + bbox.width // 2, bbox.y + bbox.height // 2), (bbox.width // 2, bbox.height // 2), 0, 0, 360, 255, -1)
        return [Detection("character", bbox, 0.20, mask=mask, label="character_fallback")]

    def _merge_overlapping(self, detections: list[Detection], width: int, height: int) -> list[Detection]:
        if not detections:
            return []
        detections = sorted(detections, key=lambda det: det.bbox.x)
        merged: list[Detection] = []
        for detection in detections:
            if not merged or self._iou(merged[-1].bbox, detection.bbox) < 0.15:
                merged.append(detection)
                continue
            prev = merged[-1]
            x1 = min(prev.bbox.x, detection.bbox.x)
            y1 = min(prev.bbox.y, detection.bbox.y)
            x2 = max(prev.bbox.x2, detection.bbox.x2)
            y2 = max(prev.bbox.y2, detection.bbox.y2)
            bbox = BoundingBox(x1, y1, x2 - x1, y2 - y1).clamp(width, height)
            mask = np.maximum(prev.mask if prev.mask is not None else 0, detection.mask if detection.mask is not None else 0)
            merged[-1] = Detection("character", bbox, max(prev.confidence, detection.confidence), mask=mask, label="character")
        return merged

    @staticmethod
    def _iou(a: BoundingBox, b: BoundingBox) -> float:
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x2, b.x2)
        y2 = min(a.y2, b.y2)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = a.area + b.area - inter
        return inter / union if union else 0.0


class GroundingDinoAdapter:
    """Small adapter boundary for GroundingDINO distributions."""

    def __init__(self, module: object, config: AppConfig) -> None:
        self.module = module
        self.config = config
        raise NotImplementedError(
            "GroundingDINO adapter requires project-specific checkpoint construction. "
            "Unset grounding_dino_checkpoint to use fallback detection."
        )

