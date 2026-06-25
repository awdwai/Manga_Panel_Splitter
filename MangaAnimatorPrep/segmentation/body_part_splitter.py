"""Body-part segmentation from pose, mask, contours, and geometry heuristics."""

from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.types import BodyPartLayer, BoundingBox, PoseKeypoint
from MangaAnimatorPrep.utils.image_utils import mask_to_bbox, normalize_mask


class BodyPartSplitter:
    """Split visible character masks into animation body-part layers."""

    PART_PARENTS = {
        "head": "torso",
        "hair": "head",
        "torso": None,
        "left_upper_arm": "torso",
        "left_lower_arm": "left_upper_arm",
        "left_hand": "left_lower_arm",
        "right_upper_arm": "torso",
        "right_lower_arm": "right_upper_arm",
        "right_hand": "right_lower_arm",
        "left_upper_leg": "torso",
        "left_lower_leg": "left_upper_leg",
        "left_foot": "left_lower_leg",
        "right_upper_leg": "torso",
        "right_lower_leg": "right_upper_leg",
        "right_foot": "right_lower_leg",
    }

    def split(self, character_mask: np.ndarray, keypoints: list[PoseKeypoint]) -> list[BodyPartLayer]:
        mask = normalize_mask(character_mask)
        bbox = mask_to_bbox(mask)
        if cv2.countNonZero(mask) == 0:
            return []
        parts: list[BodyPartLayer] = []
        kp = {point.name: point for point in keypoints}
        regions = self._geometric_regions(mask, bbox)
        for name, region_mask in regions.items():
            visible = cv2.bitwise_and(mask, region_mask)
            if cv2.countNonZero(visible) == 0:
                continue
            visible = self._largest_component(visible)
            part_bbox = mask_to_bbox(visible)
            confidence = self._confidence_for_part(name, kp)
            pivot = self._pivot_for_part(name, kp, part_bbox)
            parts.append(
                BodyPartLayer(
                    name=name,
                    mask=visible,
                    bbox=part_bbox,
                    confidence=confidence,
                    parent=self.PART_PARENTS.get(name),
                    pivot=pivot,
                )
            )
        return parts

    def _geometric_regions(self, mask: np.ndarray, bbox: BoundingBox) -> dict[str, np.ndarray]:
        height, width = mask.shape[:2]
        regions: dict[str, np.ndarray] = {}
        x0, y0, x1, y1 = bbox.x, bbox.y, bbox.x2, bbox.y2
        bw, bh = max(1, bbox.width), max(1, bbox.height)

        def rect(name: str, rx0: float, ry0: float, rx1: float, ry1: float) -> None:
            region = np.zeros((height, width), dtype=np.uint8)
            px0 = int(x0 + bw * rx0)
            py0 = int(y0 + bh * ry0)
            px1 = int(x0 + bw * rx1)
            py1 = int(y0 + bh * ry1)
            cv2.rectangle(region, (px0, py0), (px1, py1), 255, -1)
            regions[name] = region

        rect("head", 0.25, 0.00, 0.75, 0.20)
        rect("hair", 0.18, 0.00, 0.82, 0.12)
        rect("torso", 0.25, 0.18, 0.75, 0.58)
        rect("left_upper_arm", 0.00, 0.20, 0.35, 0.42)
        rect("left_lower_arm", 0.00, 0.40, 0.32, 0.62)
        rect("left_hand", 0.00, 0.58, 0.28, 0.72)
        rect("right_upper_arm", 0.65, 0.20, 1.00, 0.42)
        rect("right_lower_arm", 0.68, 0.40, 1.00, 0.62)
        rect("right_hand", 0.72, 0.58, 1.00, 0.72)
        rect("left_upper_leg", 0.28, 0.56, 0.50, 0.76)
        rect("left_lower_leg", 0.28, 0.74, 0.50, 0.94)
        rect("left_foot", 0.22, 0.90, 0.52, 1.00)
        rect("right_upper_leg", 0.50, 0.56, 0.72, 0.76)
        rect("right_lower_leg", 0.50, 0.74, 0.72, 0.94)
        rect("right_foot", 0.48, 0.90, 0.78, 1.00)
        return regions

    def _largest_component(self, mask: np.ndarray) -> np.ndarray:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if count <= 1:
            return mask
        largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        return np.where(labels == largest_label, 255, 0).astype(np.uint8)

    def _confidence_for_part(self, name: str, keypoints: dict[str, PoseKeypoint]) -> float:
        related = {
            "head": ["head", "neck"],
            "hair": ["head"],
            "torso": ["neck", "left_hip", "right_hip"],
            "left_upper_arm": ["left_shoulder", "left_elbow"],
            "left_lower_arm": ["left_elbow", "left_wrist"],
            "left_hand": ["left_wrist"],
            "right_upper_arm": ["right_shoulder", "right_elbow"],
            "right_lower_arm": ["right_elbow", "right_wrist"],
            "right_hand": ["right_wrist"],
            "left_upper_leg": ["left_hip", "left_knee"],
            "left_lower_leg": ["left_knee", "left_ankle"],
            "left_foot": ["left_ankle"],
            "right_upper_leg": ["right_hip", "right_knee"],
            "right_lower_leg": ["right_knee", "right_ankle"],
            "right_foot": ["right_ankle"],
        }[name]
        scores = [keypoints[key].confidence for key in related if key in keypoints]
        return float(max(0.15, sum(scores) / len(scores))) if scores else 0.15

    def _pivot_for_part(
        self,
        name: str,
        keypoints: dict[str, PoseKeypoint],
        bbox: BoundingBox,
    ) -> tuple[float, float]:
        pivot_key = {
            "head": "neck",
            "hair": "head",
            "torso": "neck",
            "left_upper_arm": "left_shoulder",
            "left_lower_arm": "left_elbow",
            "left_hand": "left_wrist",
            "right_upper_arm": "right_shoulder",
            "right_lower_arm": "right_elbow",
            "right_hand": "right_wrist",
            "left_upper_leg": "left_hip",
            "left_lower_leg": "left_knee",
            "left_foot": "left_ankle",
            "right_upper_leg": "right_hip",
            "right_lower_leg": "right_knee",
            "right_foot": "right_ankle",
        }.get(name)
        if pivot_key and pivot_key in keypoints:
            point = keypoints[pivot_key]
            return (float(point.x), float(point.y))
        return (float(bbox.x + bbox.width / 2), float(bbox.y + bbox.height / 2))

