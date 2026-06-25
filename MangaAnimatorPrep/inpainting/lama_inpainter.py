"""Background reconstruction using LaMa-ready backend with safe fallbacks."""

from __future__ import annotations

import importlib
import logging

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.utils.image_utils import normalize_mask
from MangaAnimatorPrep.utils.model_cache import GLOBAL_MODEL_CACHE

LOGGER = logging.getLogger(__name__)


class LaMaInpainter:
    """Reconstruct backgrounds after removing character masks."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def inpaint(self, image: np.ndarray, removal_mask: np.ndarray) -> np.ndarray:
        mask = normalize_mask(removal_mask)
        if cv2.countNonZero(mask) == 0:
            return image.copy()
        try:
            backend = self._load_lama_if_configured()
        except Exception as exc:  # pragma: no cover - optional backend
            LOGGER.warning("LaMa backend could not be loaded, using OpenCV fallback: %s", exc)
            backend = None
        if backend is not None:
            try:
                return backend.inpaint(image, mask)
            except Exception as exc:  # pragma: no cover - optional backend
                LOGGER.warning("LaMa backend failed, trying fallback: %s", exc)
        return self._opencv_inpaint(image, mask)

    def _load_lama_if_configured(self) -> object | None:
        if not self.config.models.lama_checkpoint:
            return None

        def loader() -> object:
            module = importlib.import_module("saicinpainting")
            return LaMaAdapter(module, self.config)

        return GLOBAL_MODEL_CACHE.get_or_load("lama", loader).value

    def _opencv_inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        dilated = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=1)
        radius = max(3, min(image.shape[:2]) // 80)
        telea = cv2.inpaint(bgr, dilated, radius, cv2.INPAINT_TELEA)
        ns = cv2.inpaint(telea, dilated, max(1, radius // 2), cv2.INPAINT_NS)
        return cv2.cvtColor(ns, cv2.COLOR_BGR2RGB)


class LaMaAdapter:
    """Adapter boundary for checkpoint-specific LaMa construction."""

    def __init__(self, module: object, config: AppConfig) -> None:
        self.module = module
        self.config = config
        if not config.models.lama_checkpoint:
            raise RuntimeError("LaMa checkpoint path is required")
        # LaMa distributions expose different application APIs. Validate the package and
        # checkpoint early, then use the explicit OpenCV fallback unless a callable pipeline
        # object is available from the installed package.
        self.pipeline = getattr(module, "inpaint", None)

    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        if not callable(self.pipeline):
            raise RuntimeError("Installed LaMa package does not expose a callable inpaint API")
        result = self.pipeline(image=image, mask=mask, checkpoint=str(self.config.models.lama_checkpoint))
        result_array = np.asarray(result)
        if result_array.shape[:2] != image.shape[:2]:
            raise RuntimeError("LaMa result shape does not match input image")
        if result_array.ndim == 2:
            result_array = cv2.cvtColor(result_array, cv2.COLOR_GRAY2RGB)
        return result_array[:, :, :3].astype(np.uint8)

