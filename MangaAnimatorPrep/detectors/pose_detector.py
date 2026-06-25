"""Pose estimation with MediaPipe backend and geometric fallback."""

from __future__ import annotations

import importlib
import logging

import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.types import BoundingBox, PoseKeypoint
from MangaAnimatorPrep.utils.image_utils import normalize_mask
from MangaAnimatorPrep.utils.model_cache import GLOBAL_MODEL_CACHE

LOGGER = logging.getLogger(__name__)


class PoseDetector:
    """Estimate visible body keypoints for rigging."""

    KEYPOINTS = [
        "head",
        "neck",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    ]

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def estimate(self, image: np.ndarray, character_mask: np.ndarray | None, bbox: BoundingBox) -> list[PoseKeypoint]:
        mediapipe_pose = self._load_mediapipe()
        if mediapipe_pose is not None:
            try:
                keypoints = self._estimate_mediapipe(mediapipe_pose, image)
                if keypoints:
                    return keypoints
            except Exception as exc:  # pragma: no cover - optional backend
                LOGGER.warning("MediaPipe pose failed, using geometric fallback: %s", exc)
        return self._estimate_geometric(character_mask, bbox)

    def _load_mediapipe(self) -> object | None:
        def loader() -> object | None:
            try:
                mp = importlib.import_module("mediapipe")
            except Exception as exc:  # pragma: no cover - optional dependency
                LOGGER.info("MediaPipe unavailable: %s", exc)
                return None
            return mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1, enable_segmentation=False)

        return GLOBAL_MODEL_CACHE.get_or_load("mediapipe_pose", loader).value

    def _estimate_mediapipe(self, pose: object, image: np.ndarray) -> list[PoseKeypoint]:
        results = pose.process(image)
        landmarks = getattr(results, "pose_landmarks", None)
        if not landmarks:
            return []
        height, width = image.shape[:2]
        lm = landmarks.landmark
        mapping = {
            "head": 0,
            "left_shoulder": 11,
            "right_shoulder": 12,
            "left_elbow": 13,
            "right_elbow": 14,
            "left_wrist": 15,
            "right_wrist": 16,
            "left_hip": 23,
            "right_hip": 24,
            "left_knee": 25,
            "right_knee": 26,
            "left_ankle": 27,
            "right_ankle": 28,
        }
        keypoints = [
            PoseKeypoint(name, float(lm[index].x * width), float(lm[index].y * height), float(lm[index].visibility))
            for name, index in mapping.items()
        ]
        shoulders = [kp for kp in keypoints if kp.name in {"left_shoulder", "right_shoulder"}]
        if len(shoulders) == 2:
            keypoints.append(
                PoseKeypoint("neck", (shoulders[0].x + shoulders[1].x) / 2, (shoulders[0].y + shoulders[1].y) / 2, min(shoulders[0].confidence, shoulders[1].confidence))
            )
        return keypoints

    def _estimate_geometric(self, character_mask: np.ndarray | None, bbox: BoundingBox) -> list[PoseKeypoint]:
        if character_mask is not None and np.count_nonzero(normalize_mask(character_mask)) > 0:
            ys, xs = np.where(normalize_mask(character_mask) > 0)
            x, y = float(xs.mean()), float(ys.min())
            left, right = float(xs.min()), float(xs.max())
            top, bottom = float(ys.min()), float(ys.max())
        else:
            left, right = float(bbox.x), float(bbox.x2)
            top, bottom = float(bbox.y), float(bbox.y2)
            x, y = (left + right) / 2.0, top
        width = max(1.0, right - left)
        height = max(1.0, bottom - top)
        cx = (left + right) / 2.0
        points = {
            "head": (cx, top + height * 0.10, 0.35),
            "neck": (cx, top + height * 0.22, 0.35),
            "left_shoulder": (left + width * 0.30, top + height * 0.26, 0.30),
            "right_shoulder": (left + width * 0.70, top + height * 0.26, 0.30),
            "left_elbow": (left + width * 0.18, top + height * 0.45, 0.25),
            "right_elbow": (left + width * 0.82, top + height * 0.45, 0.25),
            "left_wrist": (left + width * 0.12, top + height * 0.62, 0.22),
            "right_wrist": (left + width * 0.88, top + height * 0.62, 0.22),
            "left_hip": (left + width * 0.38, top + height * 0.58, 0.30),
            "right_hip": (left + width * 0.62, top + height * 0.58, 0.30),
            "left_knee": (left + width * 0.38, top + height * 0.78, 0.22),
            "right_knee": (left + width * 0.62, top + height * 0.78, 0.22),
            "left_ankle": (left + width * 0.38, bottom, 0.20),
            "right_ankle": (left + width * 0.62, bottom, 0.20),
        }
        _ = (x, y)
        return [PoseKeypoint(name, px, py, confidence) for name, (px, py, confidence) in points.items()]

