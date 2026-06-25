"""Interactive click-to-segment mask editing tools.

This module provides a local, deterministic SAM-like interaction layer. When SAM2 is
available in the future, this class is the integration boundary for replacing the
OpenCV fallback refinement with model prompts while preserving GUI behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np

from MangaAnimatorPrep.types import BoundingBox
from MangaAnimatorPrep.utils.image_utils import mask_to_bbox, normalize_mask


PromptKind = Literal["positive", "negative"]


@dataclass(slots=True)
class PromptPoint:
    x: int
    y: int
    kind: PromptKind


@dataclass(slots=True)
class PivotPoint:
    name: str
    x: float
    y: float


@dataclass(slots=True)
class MaskLayer:
    layer_id: str
    label: str
    mask: np.ndarray
    confidence: float
    prompts: list[PromptPoint] = field(default_factory=list)
    bbox: BoundingBox | None = None
    visible: bool = True
    locked: bool = False
    parent_id: str | None = None
    pivots: list[PivotPoint] = field(default_factory=list)

    def refresh_bbox(self) -> None:
        self.bbox = mask_to_bbox(self.mask) if cv2.countNonZero(normalize_mask(self.mask)) else None


class InteractiveSegmentationSession:
    """Manage independent interactive masks and edit operations."""

    LABELS = [
        "Head",
        "Hair",
        "Torso",
        "Upper Arm",
        "Lower Arm",
        "Hand",
        "Upper Leg",
        "Lower Leg",
        "Foot",
        "Eye",
        "Eyebrow",
        "Mouth",
        "Weapon",
        "Cape",
        "Clothing",
        "Accessory",
        "Speech Bubble",
        "Background",
    ]

    def __init__(self, image: np.ndarray) -> None:
        self.image = image
        self.height, self.width = image.shape[:2]
        self.layers: list[MaskLayer] = []
        self.active_layer_id: str | None = None

    @property
    def active_layer(self) -> MaskLayer | None:
        for layer in self.layers:
            if layer.layer_id == self.active_layer_id:
                return layer
        return None

    def new_layer_from_click(self, x: int, y: int) -> MaskLayer:
        prompt = PromptPoint(*self._clamp_point(x, y), "positive")
        mask = self._mask_from_prompt(prompt)
        label, confidence = self.suggest_label(mask, prompt.x, prompt.y)
        layer = MaskLayer(
            layer_id=f"layer_{len(self.layers) + 1:03d}",
            label=label,
            mask=mask,
            confidence=confidence,
            prompts=[prompt],
            pivots=self._default_pivots(mask, label),
        )
        layer.refresh_bbox()
        self.layers.append(layer)
        self.active_layer_id = layer.layer_id
        return layer

    def add_prompt(self, x: int, y: int, positive: bool = True) -> MaskLayer:
        layer = self.active_layer
        if layer is None:
            return self.new_layer_from_click(x, y)
        if layer.locked:
            return layer
        prompt = PromptPoint(*self._clamp_point(x, y), "positive" if positive else "negative")
        layer.prompts.append(prompt)
        prompt_mask = self._mask_from_prompt(prompt)
        if positive:
            layer.mask = cv2.bitwise_or(normalize_mask(layer.mask), prompt_mask)
        else:
            layer.mask = cv2.bitwise_and(normalize_mask(layer.mask), cv2.bitwise_not(prompt_mask))
        layer.mask = self.fill_holes(layer.mask)
        layer.refresh_bbox()
        layer.label, layer.confidence = self.suggest_label(layer.mask, prompt.x, prompt.y)
        layer.pivots = self._default_pivots(layer.mask, layer.label)
        return layer

    def rename_active(self, label: str) -> None:
        if self.active_layer and not self.active_layer.locked:
            self.active_layer.label = label

    def duplicate_active(self) -> MaskLayer | None:
        layer = self.active_layer
        if layer is None:
            return None
        duplicate = MaskLayer(
            layer_id=f"layer_{len(self.layers) + 1:03d}",
            label=f"{layer.label} Copy",
            mask=layer.mask.copy(),
            confidence=layer.confidence,
            prompts=list(layer.prompts),
            bbox=layer.bbox,
            visible=layer.visible,
            locked=False,
            parent_id=layer.parent_id,
            pivots=list(layer.pivots),
        )
        self.layers.append(duplicate)
        self.active_layer_id = duplicate.layer_id
        return duplicate

    def delete_active(self) -> None:
        self.layers = [layer for layer in self.layers if layer.layer_id != self.active_layer_id]
        self.active_layer_id = self.layers[-1].layer_id if self.layers else None

    def merge_layers(self, layer_ids: list[str], label: str = "Merged Layer") -> MaskLayer | None:
        selected = [layer for layer in self.layers if layer.layer_id in set(layer_ids)]
        if not selected:
            return None
        merged_mask = np.zeros((self.height, self.width), dtype=np.uint8)
        for layer in selected:
            merged_mask = cv2.bitwise_or(merged_mask, normalize_mask(layer.mask))
        self.layers = [layer for layer in self.layers if layer.layer_id not in set(layer_ids)]
        merged = MaskLayer(
            layer_id=f"layer_{len(self.layers) + 1:03d}",
            label=label,
            mask=merged_mask,
            confidence=max(layer.confidence for layer in selected),
        )
        merged.refresh_bbox()
        merged.pivots = self._default_pivots(merged.mask, merged.label)
        self.layers.append(merged)
        self.active_layer_id = merged.layer_id
        return merged

    def set_visibility(self, layer_id: str, visible: bool) -> None:
        layer = self._find(layer_id)
        if layer:
            layer.visible = visible

    def set_lock(self, layer_id: str, locked: bool) -> None:
        layer = self._find(layer_id)
        if layer:
            layer.locked = locked

    def brush(self, x: int, y: int, radius: int, erase: bool = False) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        x, y = self._clamp_point(x, y)
        edit = np.zeros((self.height, self.width), dtype=np.uint8)
        cv2.circle(edit, (x, y), max(1, radius), 255, -1)
        if erase:
            layer.mask = cv2.bitwise_and(normalize_mask(layer.mask), cv2.bitwise_not(edit))
        else:
            layer.mask = cv2.bitwise_or(normalize_mask(layer.mask), edit)
        layer.refresh_bbox()

    def rectangle_select(self, bbox: BoundingBox, add: bool = True) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        rect_mask = np.zeros((self.height, self.width), dtype=np.uint8)
        bbox = bbox.clamp(self.width, self.height)
        rect_mask[bbox.y : bbox.y2, bbox.x : bbox.x2] = 255
        layer.mask = cv2.bitwise_or(layer.mask, rect_mask) if add else cv2.bitwise_and(layer.mask, cv2.bitwise_not(rect_mask))
        layer.refresh_bbox()

    def polygon_lasso(self, points: list[tuple[int, int]], add: bool = True) -> None:
        layer = self.active_layer
        if layer is None or layer.locked or len(points) < 3:
            return
        poly_mask = np.zeros((self.height, self.width), dtype=np.uint8)
        cv2.fillPoly(poly_mask, [np.array(points, dtype=np.int32)], 255)
        layer.mask = cv2.bitwise_or(layer.mask, poly_mask) if add else cv2.bitwise_and(layer.mask, cv2.bitwise_not(poly_mask))
        layer.refresh_bbox()

    def magic_wand(self, x: int, y: int, add: bool = True) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        wand = self._mask_from_prompt(PromptPoint(*self._clamp_point(x, y), "positive"))
        layer.mask = cv2.bitwise_or(layer.mask, wand) if add else cv2.bitwise_and(layer.mask, cv2.bitwise_not(wand))
        layer.refresh_bbox()

    def smooth_active(self, kernel_size: int = 5) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        layer.mask = self.smooth(layer.mask, kernel_size)
        layer.refresh_bbox()

    def expand_active(self, pixels: int = 3) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        layer.mask = self.expand(layer.mask, pixels)
        layer.refresh_bbox()

    def contract_active(self, pixels: int = 3) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        layer.mask = self.contract(layer.mask, pixels)
        layer.refresh_bbox()

    def fill_holes_active(self) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        layer.mask = self.fill_holes(layer.mask)
        layer.refresh_bbox()

    def feather_active(self, pixels: int = 3) -> None:
        layer = self.active_layer
        if layer is None or layer.locked:
            return
        layer.mask = self.feather(layer.mask, pixels)
        layer.refresh_bbox()

    @staticmethod
    def smooth(mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        return cv2.morphologyEx(normalize_mask(mask), cv2.MORPH_OPEN, kernel)

    @staticmethod
    def expand(mask: np.ndarray, pixels: int = 3) -> np.ndarray:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * pixels + 1, 2 * pixels + 1))
        return cv2.dilate(normalize_mask(mask), kernel, iterations=1)

    @staticmethod
    def contract(mask: np.ndarray, pixels: int = 3) -> np.ndarray:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * pixels + 1, 2 * pixels + 1))
        return cv2.erode(normalize_mask(mask), kernel, iterations=1)

    @staticmethod
    def fill_holes(mask: np.ndarray) -> np.ndarray:
        normalized = normalize_mask(mask)
        flood = normalized.copy()
        h, w = normalized.shape[:2]
        cv2.floodFill(flood, np.zeros((h + 2, w + 2), dtype=np.uint8), (0, 0), 255)
        return cv2.bitwise_or(normalized, cv2.bitwise_not(flood))

    @staticmethod
    def feather(mask: np.ndarray, pixels: int = 3) -> np.ndarray:
        blur_size = max(3, 2 * pixels + 1)
        if blur_size % 2 == 0:
            blur_size += 1
        return cv2.GaussianBlur(normalize_mask(mask), (blur_size, blur_size), 0)

    def suggest_label(self, mask: np.ndarray, x: int, y: int) -> tuple[str, float]:
        normalized = normalize_mask(mask)
        pixels = self.image[normalized > 0]
        if len(pixels) == 0:
            return "Accessory", 0.10
        bbox = mask_to_bbox(normalized)
        area_ratio = cv2.countNonZero(normalized) / max(1, self.width * self.height)
        mean = pixels.mean(axis=0)
        brightness = float(mean.mean())
        y_ratio = y / max(1, self.height)
        aspect = bbox.width / max(1, bbox.height)
        if area_ratio > 0.45:
            return "Background", 0.65
        if brightness > 225 and 0.5 < aspect < 4.5:
            return "Speech Bubble", 0.62
        if brightness < 80 and y_ratio < 0.35:
            return "Hair", 0.60
        if area_ratio < 0.015 and brightness < 100 and y_ratio < 0.45:
            return "Eye", 0.52
        if area_ratio < 0.02 and 0.35 <= y_ratio <= 0.60:
            return "Mouth", 0.45
        if bbox.height > bbox.width * 2.5 or bbox.width > bbox.height * 2.5:
            return "Weapon", 0.42
        if y_ratio < 0.35:
            return "Head", 0.50
        if y_ratio < 0.65:
            return "Clothing", 0.42
        return "Accessory", 0.35

    def _mask_from_prompt(self, prompt: PromptPoint) -> np.ndarray:
        seed = (prompt.x, prompt.y)
        image_bgr = cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR)
        flood_mask = np.zeros((self.height + 2, self.width + 2), dtype=np.uint8)
        flood_image = image_bgr.copy()
        lo_diff = (24, 24, 24)
        up_diff = (24, 24, 24)
        cv2.floodFill(flood_image, flood_mask, seed, (255, 0, 255), lo_diff, up_diff, cv2.FLOODFILL_FIXED_RANGE)
        result = flood_mask[1:-1, 1:-1] * 255
        if cv2.countNonZero(result) < 20:
            result = self._grabcut_around_point(prompt.x, prompt.y)
        return normalize_mask(result)

    def _grabcut_around_point(self, x: int, y: int) -> np.ndarray:
        size = max(40, min(self.width, self.height) // 5)
        x0 = max(0, x - size // 2)
        y0 = max(0, y - size // 2)
        x1 = min(self.width - 1, x + size // 2)
        y1 = min(self.height - 1, y + size // 2)
        rect = (x0, y0, max(1, x1 - x0), max(1, y1 - y0))
        mask = np.zeros((self.height, self.width), dtype=np.uint8)
        bgd = np.zeros((1, 65), dtype=np.float64)
        fgd = np.zeros((1, 65), dtype=np.float64)
        try:
            cv2.grabCut(cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR), mask, rect, bgd, fgd, 2, cv2.GC_INIT_WITH_RECT)
            return np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        except cv2.error:
            fallback = np.zeros((self.height, self.width), dtype=np.uint8)
            cv2.circle(fallback, (x, y), max(8, size // 6), 255, -1)
            return fallback

    def _default_pivots(self, mask: np.ndarray, label: str) -> list[PivotPoint]:
        if cv2.countNonZero(normalize_mask(mask)) == 0:
            return []
        bbox = mask_to_bbox(mask)
        cx = bbox.x + bbox.width / 2
        cy = bbox.y + bbox.height / 2
        if label in {"Head", "Hair"}:
            return [PivotPoint("Head Pivot", cx, bbox.y2)]
        if label in {"Upper Arm", "Lower Arm", "Hand"}:
            return [PivotPoint("Shoulder/Elbow/Wrist Pivot", cx, cy)]
        if label in {"Upper Leg", "Lower Leg", "Foot"}:
            return [PivotPoint("Hip/Knee/Ankle Pivot", cx, cy)]
        return [PivotPoint(f"{label} Pivot", cx, cy)]

    def _clamp_point(self, x: int, y: int) -> tuple[int, int]:
        return (max(0, min(int(x), self.width - 1)), max(0, min(int(y), self.height - 1)))

    def _find(self, layer_id: str) -> MaskLayer | None:
        return next((layer for layer in self.layers if layer.layer_id == layer_id), None)

