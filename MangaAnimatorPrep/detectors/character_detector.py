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
        try:
            backend = self._load_grounding_dino_if_configured()
        except Exception as exc:  # pragma: no cover - optional backend
            LOGGER.warning("GroundingDINO backend could not be loaded, using fallback: %s", exc)
            backend = None
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
        dark = self._remove_border_connected(dark)
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=2)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
        dark = self._remove_border_connected(dark)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            detections.extend(self._detections_from_contour(contour, dark, width, height, min_area))

        detections = self._deduplicate(detections)
        if detections:
            return sorted(detections, key=lambda det: (det.bbox.x, det.bbox.y))

        # Fallback for sparse panels: provide a conservative central visible-character region.
        bbox = BoundingBox(width // 4, height // 5, width // 2, int(height * 0.70)).clamp(width, height)
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.ellipse(mask, (bbox.x + bbox.width // 2, bbox.y + bbox.height // 2), (bbox.width // 2, bbox.height // 2), 0, 0, 360, 255, -1)
        return [Detection("character", bbox, 0.20, mask=mask, label="character_fallback")]

    def _detections_from_contour(
        self,
        contour: np.ndarray,
        dark_mask: np.ndarray,
        width: int,
        height: int,
        min_area: int,
    ) -> list[Detection]:
        x, y, w, h = cv2.boundingRect(contour)
        bbox = BoundingBox(x, y, w, h).pad(4, width, height)
        if bbox.area < min_area or bbox.height < height * 0.18:
            return []
        if bbox.width > width * 0.96 and bbox.height > height * 0.96:
            return []

        contour_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, thickness=cv2.FILLED)
        split_masks = self._split_connected_character_mask(contour_mask, bbox)
        detections: list[Detection] = []
        for mask in split_masks:
            split_bbox = self._mask_bbox(mask).pad(4, width, height)
            if split_bbox.area < min_area:
                continue
            mask = cv2.bitwise_and(mask, dark_mask)
            if cv2.countNonZero(mask) < max(20, min_area * 0.12):
                continue
            split_bbox = self._mask_bbox(mask).pad(4, width, height)
            confidence = min(0.85, 0.35 + split_bbox.area / max(1.0, width * height))
            detections.append(Detection("character", split_bbox, confidence, mask=mask, label="character", contour=contour))
        return detections

    def _split_connected_character_mask(self, mask: np.ndarray, bbox: BoundingBox) -> list[np.ndarray]:
        crop = mask[bbox.y : bbox.y2, bbox.x : bbox.x2]
        if crop.size == 0:
            return [mask]
        distance = cv2.distanceTransform(crop, cv2.DIST_L2, 5)
        if float(distance.max(initial=0.0)) < 3.0:
            return [mask]
        _, sure_fg = cv2.threshold(distance, 0.45 * float(distance.max()), 255, cv2.THRESH_BINARY)
        sure_fg = sure_fg.astype(np.uint8)
        count, markers = cv2.connectedComponents(sure_fg)
        if count <= 2:
            return self._projection_split(mask, bbox)

        local_markers = markers + 1
        local_markers[crop == 0] = 0
        color_crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
        watershed = cv2.watershed(color_crop, local_markers.astype(np.int32))
        split_masks: list[np.ndarray] = []
        for label in sorted(set(np.unique(watershed)) - {-1, 0, 1}):
            local = np.where(watershed == label, 255, 0).astype(np.uint8)
            if cv2.countNonZero(local) < 30:
                continue
            full = np.zeros_like(mask)
            full[bbox.y : bbox.y2, bbox.x : bbox.x2] = local
            split_masks.append(full)
        return split_masks or self._projection_split(mask, bbox)

    def _projection_split(self, mask: np.ndarray, bbox: BoundingBox) -> list[np.ndarray]:
        crop = mask[bbox.y : bbox.y2, bbox.x : bbox.x2]
        projection = np.count_nonzero(crop > 0, axis=0)
        if len(projection) < 40:
            return [mask]
        threshold = max(2, int(projection.max(initial=0) * 0.18))
        valleys = np.where(projection <= threshold)[0]
        split_points: list[int] = []
        if len(valleys):
            groups = np.split(valleys, np.where(np.diff(valleys) > 1)[0] + 1)
            for group in groups:
                center = int(group[len(group) // 2])
                if crop.shape[1] * 0.20 < center < crop.shape[1] * 0.80:
                    split_points.append(center)
        if not split_points:
            return [mask]
        masks: list[np.ndarray] = []
        start = 0
        for split in split_points[:3] + [crop.shape[1]]:
            if split - start < 12:
                continue
            local = np.zeros_like(crop)
            local[:, start:split] = crop[:, start:split]
            if cv2.countNonZero(local) > 30:
                full = np.zeros_like(mask)
                full[bbox.y : bbox.y2, bbox.x : bbox.x2] = local
                masks.append(full)
            start = split
        return masks or [mask]

    def _deduplicate(self, detections: list[Detection]) -> list[Detection]:
        if not detections:
            return []
        detections = sorted(detections, key=lambda det: det.confidence, reverse=True)
        kept: list[Detection] = []
        for detection in detections:
            if any(self._iou(detection.bbox, existing.bbox) > 0.82 for existing in kept):
                continue
            kept.append(detection)
        return kept

    def _mask_bbox(self, mask: np.ndarray) -> BoundingBox:
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            return BoundingBox(0, 0, 1, 1)
        return BoundingBox(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))

    def _remove_border_connected(self, mask: np.ndarray) -> np.ndarray:
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
        if not config.models.grounding_dino_config or not config.models.grounding_dino_checkpoint:
            raise RuntimeError("GroundingDINO requires both config and checkpoint paths")
        load_model = getattr(module, "load_model", None)
        if load_model is None:
            raise RuntimeError("groundingdino.util.inference.load_model is unavailable")
        torch = importlib.import_module("torch")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            self.model = load_model(
                str(config.models.grounding_dino_config),
                str(config.models.grounding_dino_checkpoint),
                device=self.device,
            )
        except TypeError:
            self.model = load_model(str(config.models.grounding_dino_config), str(config.models.grounding_dino_checkpoint))

    def detect(self, panel: np.ndarray) -> list[Detection]:
        predict = getattr(self.module, "predict", None)
        if predict is None:
            raise RuntimeError("groundingdino.util.inference.predict is unavailable")
        try:
            boxes, logits, phrases = predict(
                model=self.model,
                image=panel,
                caption="person . character . face . body .",
                box_threshold=self.config.confidence_threshold,
                text_threshold=0.25,
                device=self.device,
            )
        except TypeError:
            boxes, logits, phrases = predict(
                self.model,
                panel,
                "person . character . face . body .",
                self.config.confidence_threshold,
                0.25,
            )
        return self._to_detections(panel, boxes, logits, phrases)

    def _to_detections(self, panel: np.ndarray, boxes: object, logits: object, phrases: object) -> list[Detection]:
        height, width = panel.shape[:2]
        box_array = self._as_numpy(boxes)
        logit_array = self._as_numpy(logits).reshape(-1) if logits is not None else np.ones((len(box_array),), dtype=np.float32)
        phrase_list = list(phrases) if phrases is not None else ["character"] * len(box_array)
        detections: list[Detection] = []
        for idx, raw_box in enumerate(box_array):
            if len(raw_box) < 4:
                continue
            x1, y1, x2, y2 = self._convert_box(raw_box[:4], width, height)
            bbox = BoundingBox(x1, y1, x2 - x1, y2 - y1).clamp(width, height)
            if bbox.area <= 0:
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            mask[bbox.y : bbox.y2, bbox.x : bbox.x2] = 255
            confidence = float(logit_array[idx]) if idx < len(logit_array) else 0.5
            label = str(phrase_list[idx]) if idx < len(phrase_list) else "character"
            detections.append(Detection("character", bbox, confidence, mask=mask, label=label))
        return detections

    def _convert_box(self, raw_box: np.ndarray, width: int, height: int) -> tuple[int, int, int, int]:
        values = raw_box.astype(float)
        if float(np.max(values)) <= 1.5:
            cx, cy, bw, bh = values
            x1 = int((cx - bw / 2) * width)
            y1 = int((cy - bh / 2) * height)
            x2 = int((cx + bw / 2) * width)
            y2 = int((cy + bh / 2) * height)
        else:
            x1, y1, x2, y2 = [int(value) for value in values]
        return x1, y1, x2, y2

    def _as_numpy(self, value: object) -> np.ndarray:
        if hasattr(value, "detach"):
            value = value.detach().cpu().numpy()
        return np.asarray(value)

