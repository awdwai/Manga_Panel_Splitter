"""Animation layer export helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from MangaAnimatorPrep.types import BodyPartLayer, Detection, PoseKeypoint
from MangaAnimatorPrep.utils.file_utils import ensure_dir, numbered_name
from MangaAnimatorPrep.utils.image_utils import (
    crop_with_bbox,
    draw_detections,
    draw_pose,
    normalize_mask,
    overlay_mask,
    save_rgb,
    transparent_crop,
)


class LayerExporter:
    """Export panel-specific animation layers and debug images."""

    def export_panel_image(self, panel_dir: Path, panel_index: int, panel: np.ndarray) -> Path:
        ensure_dir(panel_dir)
        path = panel_dir / numbered_name("panel", panel_index)
        save_rgb(path, panel)
        return path

    def export_background(self, panel_dir: Path, background: np.ndarray) -> Path:
        path = panel_dir / "background.png"
        save_rgb(path, background)
        return path

    def export_detection_layers(self, root: Path, prefix: str, panel: np.ndarray, detections: list[Detection]) -> list[Path]:
        out_dir = ensure_dir(root / prefix)
        paths: list[Path] = []
        for index, detection in enumerate(detections, start=1):
            if detection.mask is None:
                crop = crop_with_bbox(panel, detection.bbox)
                alpha = np.full(crop.shape[:2], 255, dtype=np.uint8)
                rgba = np.dstack([crop, alpha])
            else:
                rgba = transparent_crop(panel, detection.mask, detection.bbox)
            path = out_dir / numbered_name(prefix.rstrip("s"), index)
            Image.fromarray(rgba.astype(np.uint8), mode="RGBA").save(path)
            paths.append(path)
        return paths

    def export_character(
        self,
        panel_dir: Path,
        character_index: int,
        panel: np.ndarray,
        character_mask: np.ndarray,
        body_parts: list[BodyPartLayer],
    ) -> Path:
        char_dir = ensure_dir(panel_dir / f"character_{character_index:02d}")
        full_bbox = self._mask_bbox(character_mask)
        character = transparent_crop(panel, character_mask, full_bbox)
        Image.fromarray(character.astype(np.uint8), mode="RGBA").save(char_dir / "character.png")
        for part in body_parts:
            rgba = transparent_crop(panel, part.mask, part.bbox)
            Image.fromarray(rgba.astype(np.uint8), mode="RGBA").save(char_dir / f"{part.name}.png")
        return char_dir

    def export_debug(
        self,
        panel_dir: Path,
        panel: np.ndarray,
        panels: list[Detection] | None = None,
        characters: list[Detection] | None = None,
        character_mask: np.ndarray | None = None,
        keypoints: list[PoseKeypoint] | None = None,
        body_parts: list[BodyPartLayer] | None = None,
    ) -> None:
        debug_dir = ensure_dir(panel_dir / "debug")
        if panels is not None:
            save_rgb(debug_dir / "panel_outline.png", draw_detections(panel, panels, (255, 0, 0)))
        if characters is not None:
            save_rgb(debug_dir / "character_boxes.png", draw_detections(panel, characters, (0, 0, 255)))
        if character_mask is not None:
            save_rgb(debug_dir / "character_mask.png", overlay_mask(panel, character_mask, (0, 255, 0)))
        if keypoints is not None:
            save_rgb(debug_dir / "pose_overlay.png", draw_pose(panel, keypoints))
        if body_parts:
            canvas = panel.copy()
            colors = [
                (255, 0, 0),
                (0, 255, 0),
                (0, 0, 255),
                (255, 255, 0),
                (255, 0, 255),
                (0, 255, 255),
            ]
            for idx, part in enumerate(body_parts):
                canvas = overlay_mask(canvas, part.mask, colors[idx % len(colors)], 0.25)
            save_rgb(debug_dir / "body_part_masks.png", canvas)

    def _mask_bbox(self, mask: np.ndarray):
        from MangaAnimatorPrep.utils.image_utils import mask_to_bbox

        return mask_to_bbox(normalize_mask(mask))

