"""Image loading, preprocessing, masking, and debug drawing utilities."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from MangaAnimatorPrep.config import PreprocessingConfig
from MangaAnimatorPrep.types import BoundingBox, Detection, PoseKeypoint


def load_image(path: Path) -> np.ndarray:
    """Load an image as RGB numpy array."""

    with Image.open(path) as image:
        return np.array(image.convert("RGB"))


def save_rgb(path: Path, image: np.ndarray) -> None:
    Image.fromarray(np.clip(image, 0, 255).astype(np.uint8), mode="RGB").save(path)


def save_rgba(path: Path, image: np.ndarray, mask: np.ndarray | None = None) -> None:
    rgb = ensure_rgb(image)
    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8) if mask is None else normalize_mask(mask)
    rgba = np.dstack([rgb, alpha])
    Image.fromarray(rgba, mode="RGBA").save(path)


def ensure_rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image


def normalize_mask(mask: np.ndarray) -> np.ndarray:
    if mask.dtype == np.bool_:
        return (mask.astype(np.uint8) * 255)
    if mask.max(initial=0) <= 1:
        return (mask.astype(np.uint8) * 255)
    return np.clip(mask, 0, 255).astype(np.uint8)


def crop_with_bbox(image: np.ndarray, bbox: BoundingBox) -> np.ndarray:
    return image[bbox.y : bbox.y2, bbox.x : bbox.x2].copy()


def mask_to_bbox(mask: np.ndarray) -> BoundingBox:
    ys, xs = np.where(normalize_mask(mask) > 0)
    if len(xs) == 0 or len(ys) == 0:
        return BoundingBox(0, 0, 1, 1)
    return BoundingBox(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def preprocess_manga(image: np.ndarray, config: PreprocessingConfig) -> dict[str, np.ndarray]:
    """Apply manga-specific preprocessing and return named intermediates."""

    rgb = ensure_rgb(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if config.grayscale_normalization:
        gray = cv2.equalizeHist(gray)
    denoised = cv2.fastNlMeansDenoising(gray, None, 7, 7, 21) if config.denoise else gray
    if config.screentone_removal:
        denoised = cv2.medianBlur(denoised, 3)
    if config.line_art_enhancement:
        blur = cv2.GaussianBlur(denoised, (0, 0), 1.2)
        enhanced = cv2.addWeighted(denoised, 1.5, blur, -0.5, 0)
    else:
        enhanced = denoised
    if config.adaptive_thresholding:
        threshold = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            9,
        )
    else:
        _, threshold = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if config.edge_enhancement:
        edges = cv2.Canny(enhanced, 50, 150)
        kernel = np.ones((2, 2), dtype=np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
    else:
        edges = cv2.Canny(enhanced, 80, 180)
    return {"gray": gray, "denoised": denoised, "enhanced": enhanced, "threshold": threshold, "edges": edges}


def transparent_crop(image: np.ndarray, mask: np.ndarray, bbox: BoundingBox) -> np.ndarray:
    crop = crop_with_bbox(image, bbox)
    alpha = normalize_mask(mask)[bbox.y : bbox.y2, bbox.x : bbox.x2]
    return np.dstack([crop, alpha])


def draw_detections(image: np.ndarray, detections: list[Detection], color: tuple[int, int, int] = (255, 0, 0)) -> np.ndarray:
    canvas = ensure_rgb(image).copy()
    for detection in detections:
        bbox = detection.bbox
        cv2.rectangle(canvas, (bbox.x, bbox.y), (bbox.x2, bbox.y2), color, 2)
        label = detection.label or detection.kind
        cv2.putText(
            canvas,
            f"{label}:{detection.confidence:.2f}",
            (bbox.x, max(12, bbox.y - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return canvas


def overlay_mask(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int] = (0, 255, 0), alpha: float = 0.35) -> np.ndarray:
    canvas = ensure_rgb(image).copy()
    mask_bool = normalize_mask(mask) > 0
    overlay = np.zeros_like(canvas)
    overlay[:, :] = color
    canvas[mask_bool] = cv2.addWeighted(canvas, 1 - alpha, overlay, alpha, 0)[mask_bool]
    return canvas


def draw_pose(image: np.ndarray, keypoints: list[PoseKeypoint]) -> np.ndarray:
    canvas = ensure_rgb(image).copy()
    lookup = {kp.name: kp for kp in keypoints if kp.confidence > 0.0}
    limbs = [
        ("head", "neck"),
        ("neck", "left_shoulder"),
        ("neck", "right_shoulder"),
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
        ("neck", "left_hip"),
        ("neck", "right_hip"),
        ("left_hip", "left_knee"),
        ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"),
        ("right_knee", "right_ankle"),
    ]
    for a, b in limbs:
        if a in lookup and b in lookup:
            cv2.line(canvas, (int(lookup[a].x), int(lookup[a].y)), (int(lookup[b].x), int(lookup[b].y)), (0, 255, 0), 2)
    for kp in lookup.values():
        cv2.circle(canvas, (int(kp.x), int(kp.y)), 4, (255, 0, 0), -1)
    return canvas

