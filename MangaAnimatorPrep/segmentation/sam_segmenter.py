"""Character segmentation with SAM2-ready lazy backend and efficient fallback."""

from __future__ import annotations

import importlib
import logging

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import Detection
from MangaAnimatorPrep.utils.image_utils import normalize_mask
from MangaAnimatorPrep.utils.model_cache import GLOBAL_MODEL_CACHE

LOGGER = logging.getLogger(__name__)


class SAMSegmenter:
    """Refine character detections into alpha masks."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def segment(self, image: np.ndarray, character: Detection) -> np.ndarray:
        try:
            backend = self._load_sam2_if_configured()
        except Exception as exc:  # pragma: no cover - optional backend
            LOGGER.warning("SAM2 backend could not be loaded, using fallback segmentation: %s", exc)
            backend = None
        if backend is not None:
            try:
                return backend.segment(image, character)
            except Exception as exc:  # pragma: no cover - optional backend
                LOGGER.warning("SAM2 backend failed, using fallback segmentation: %s", exc)
        return self._fallback_segment(image, character)

    def _load_sam2_if_configured(self) -> object | None:
        if not self.config.models.sam2_checkpoint:
            return None

        def loader() -> object:
            module = importlib.import_module("sam2")
            return SAM2Adapter(module, self.config)

        return GLOBAL_MODEL_CACHE.get_or_load("sam2", loader).value

    def _fallback_segment(self, image: np.ndarray, character: Detection) -> np.ndarray:
        height, width = image.shape[:2]
        bbox = character.bbox.pad(6, width, height)
        initial = np.zeros((height, width), dtype=np.uint8)
        if character.mask is not None and np.count_nonzero(character.mask) > 0:
            initial = normalize_mask(character.mask)
        else:
            initial[bbox.y : bbox.y2, bbox.x : bbox.x2] = 255

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        mask = cv2.bitwise_and(dark, initial)
        if cv2.countNonZero(mask) < max(10, bbox.area * 0.08):
            mask = initial
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
        mask = cv2.GaussianBlur(mask, (3, 3), 0)
        return normalize_mask(mask)


class SAM2Adapter:
    """Adapter boundary for project-specific SAM2 checkpoint wiring."""

    def __init__(self, module: object, config: AppConfig) -> None:
        self.module = module
        self.config = config
        if not config.models.sam2_config or not config.models.sam2_checkpoint:
            raise RuntimeError("SAM2 requires both config and checkpoint paths")
        build_module = importlib.import_module("sam2.build_sam")
        predictor_module = importlib.import_module("sam2.sam2_image_predictor")
        build_sam2 = getattr(build_module, "build_sam2", None)
        predictor_cls = getattr(predictor_module, "SAM2ImagePredictor", None)
        if build_sam2 is None or predictor_cls is None:
            raise RuntimeError("SAM2 build_sam2 or SAM2ImagePredictor API is unavailable")
        try:
            model = build_sam2(str(config.models.sam2_config), str(config.models.sam2_checkpoint), device="cuda")
        except Exception:
            model = build_sam2(str(config.models.sam2_config), str(config.models.sam2_checkpoint), device="cpu")
        self.predictor = predictor_cls(model)

    def segment(self, image: np.ndarray, character: Detection) -> np.ndarray:
        height, width = image.shape[:2]
        self.predictor.set_image(image)
        box = np.array(character.bbox.to_xyxy(), dtype=np.float32)
        masks, scores, _ = self.predictor.predict(box=box, multimask_output=True)
        if masks is None or len(masks) == 0:
            raise RuntimeError("SAM2 returned no masks")
        score_array = np.asarray(scores).reshape(-1) if scores is not None else np.zeros((len(masks),), dtype=np.float32)
        best_index = int(np.argmax(score_array)) if len(score_array) else 0
        mask = np.asarray(masks[best_index]).astype(np.uint8)
        if mask.shape != (height, width):
            mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
        return normalize_mask(mask)

