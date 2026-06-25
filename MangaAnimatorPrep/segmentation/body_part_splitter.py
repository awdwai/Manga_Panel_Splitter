"""Body-part export from approved semantic/correction masks."""

from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.types import BodyPartLayer, BoundingBox, PoseKeypoint
from MangaAnimatorPrep.utils.image_utils import mask_to_bbox, normalize_mask


class BodyPartSplitter:
    """Export visible body parts only after semantic/user-approved masks exist."""

    BODY_PARTS = [
        "head",
        "hair",
        "torso",
        "left_upper_arm",
        "left_lower_arm",
        "left_hand",
        "right_upper_arm",
        "right_lower_arm",
        "right_hand",
        "left_upper_leg",
        "left_lower_leg",
        "left_foot",
        "right_upper_leg",
        "right_lower_leg",
        "right_foot",
    ]

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
        "glasses": "head",
        "hat": "head",
        "weapon": "torso",
        "accessory": "torso",
    }

    def split(self, character_mask: np.ndarray, keypoints: list[PoseKeypoint]) -> list[BodyPartLayer]:
        """Compatibility wrapper returning visible body-part layers only."""

        parts, _ = self.analyze(character_mask, keypoints)
        return parts

    def analyze(
        self,
        character_mask: np.ndarray,
        keypoints: list[PoseKeypoint],
        panel: np.ndarray | None = None,
        ambiguous_mask: np.ndarray | None = None,
        approved_body_part_masks: dict[str, np.ndarray] | None = None,
    ) -> tuple[list[BodyPartLayer], dict[str, object]]:
        """Return visible layers plus complete visibility metadata.

        The analyzer only exports masks for visible pixels. Hidden, cropped, or uncertain
        anatomy is represented in metadata instead of generating empty or hallucinated PNGs.
        """

        mask = normalize_mask(character_mask)
        bbox = mask_to_bbox(mask)
        if not approved_body_part_masks:
            return [], self._approval_required_metadata(bbox)
        if cv2.countNonZero(mask) == 0:
            return [], {
                "bbox": bbox.to_dict(),
                "visible_body_parts": [],
                "missing_body_parts": self.BODY_PARTS,
                "body_parts": {
                    name: {"status": "Missing", "confidence": 0.0, "bbox": None, "reason": "empty_character_mask"}
                    for name in self.BODY_PARTS
                },
                "warnings": ["Character mask is empty; no body parts exported."],
                "small_objects": {},
            }

        parts: list[BodyPartLayer] = []
        kp = {point.name: point for point in keypoints}
        regions = {
            name: normalize_mask(approved_body_part_masks.get(name, np.zeros_like(mask)))
            for name in self.BODY_PARTS
        }
        ambiguous = normalize_mask(ambiguous_mask) if ambiguous_mask is not None else np.zeros_like(mask)
        metadata: dict[str, object] = {
            "bbox": bbox.to_dict(),
            "visible_body_parts": [],
            "missing_body_parts": [],
            "body_parts": {},
            "warnings": [],
            "small_objects": {},
        }
        body_metadata: dict[str, dict[str, object]] = {}
        visible_names: list[str] = []
        missing_names: list[str] = []

        for name in self.BODY_PARTS:
            region_mask = regions[name]
            visible = cv2.bitwise_and(mask, region_mask)
            visible_pixels = int(cv2.countNonZero(visible))
            expected_pixels = max(1, int(cv2.countNonZero(region_mask)))
            visible_ratio = visible_pixels / expected_pixels
            status, reason = self._classify_visibility(name, bbox, mask.shape, visible_pixels, visible_ratio)
            confidence = self._confidence_for_part(name, kp, visible_ratio, status)
            if status != "Visible":
                body_metadata[name] = {
                    "status": status,
                    "confidence": confidence,
                    "bbox": None,
                    "reason": reason,
                    "visible_pixel_ratio": visible_ratio,
                }
                missing_names.append(name)
                continue
            visible = self._largest_component(visible)
            part_bbox = mask_to_bbox(visible)
            pivot = self._pivot_for_part(name, kp, part_bbox)
            ambiguous_pixels = int(cv2.countNonZero(cv2.bitwise_and(visible, ambiguous)))
            parts.append(
                BodyPartLayer(
                    name=name,
                    mask=visible,
                    bbox=part_bbox,
                    confidence=confidence,
                    parent=self.PART_PARENTS.get(name),
                    pivot=pivot,
                    status=status,
                    ambiguous_pixels=ambiguous_pixels,
                    metadata={"reason": reason, "visible_pixel_ratio": visible_ratio},
                )
            )
            body_metadata[name] = {
                "status": status,
                "confidence": confidence,
                "bbox": part_bbox.to_dict(),
                "reason": reason,
                "visible_pixel_ratio": visible_ratio,
                "ambiguous_pixels": ambiguous_pixels,
                "layer": f"{name}.png",
            }
            visible_names.append(name)

        if panel is not None:
            accessory_parts, accessory_metadata = self._detect_small_objects(panel, mask, bbox)
            parts.extend(accessory_parts)
            metadata["small_objects"] = accessory_metadata

        if missing_names:
            warnings = metadata["warnings"]
            assert isinstance(warnings, list)
            warnings.append("Some anatomy is missing, occluded, out of frame, or uncertain; exported rig is partial.")

        metadata["visible_body_parts"] = visible_names
        metadata["missing_body_parts"] = missing_names
        metadata["body_parts"] = body_metadata
        return parts, metadata

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

    def _approval_required_metadata(self, bbox: BoundingBox) -> dict[str, object]:
        return {
            "bbox": bbox.to_dict(),
            "visible_body_parts": [],
            "missing_body_parts": self.BODY_PARTS,
            "body_parts": {
                name: {
                    "status": "Unknown",
                    "confidence": 0.0,
                    "bbox": None,
                    "reason": "body_part_masks_not_approved",
                    "requires_user_correction": True,
                }
                for name in self.BODY_PARTS
            },
            "warnings": [
                "Body parts were not generated because approved semantic body-part masks are required.",
                "Use the GUI verification/correction workflow before exporting body-part layers.",
            ],
            "small_objects": {},
            "approval_required": True,
        }

    def _classify_visibility(
        self,
        name: str,
        bbox: BoundingBox,
        shape: tuple[int, int],
        visible_pixels: int,
        visible_ratio: float,
    ) -> tuple[str, str]:
        height, width = shape
        min_pixels = max(16, int(bbox.area * 0.006))
        if visible_pixels < min_pixels or visible_ratio < 0.025:
            if self._part_likely_out_of_frame(name, bbox, width, height):
                return "Out of Frame", "expected_region_extends_to_panel_crop"
            return "Unknown", "insufficient_visible_pixels"

        aspect = bbox.height / max(1, bbox.width)
        panel_ratio = bbox.height / max(1, height)
        lower_body = {
            "left_upper_leg",
            "left_lower_leg",
            "left_foot",
            "right_upper_leg",
            "right_lower_leg",
            "right_foot",
        }
        arm_or_hand = {
            "left_upper_arm",
            "left_lower_arm",
            "left_hand",
            "right_upper_arm",
            "right_lower_arm",
            "right_hand",
        }
        if name in lower_body and (aspect < 1.25 or panel_ratio < 0.38):
            return "Out of Frame", "character_extent_suggests_lower_body_not_visible"
        if name == "torso" and panel_ratio < 0.18:
            return "Unknown", "close_up_or_small_visible_region"
        if name in arm_or_hand and visible_ratio < 0.08:
            return "Occluded", "limb_region_has_low_visible_support"
        return "Visible", "visible_pixels_detected"

    def _part_likely_out_of_frame(self, name: str, bbox: BoundingBox, width: int, height: int) -> bool:
        margin = 3
        if name.startswith("left_") and bbox.x <= margin:
            return True
        if name.startswith("right_") and bbox.x2 >= width - margin:
            return True
        if name in {"left_lower_leg", "left_foot", "right_lower_leg", "right_foot"} and bbox.y2 >= height - margin:
            return True
        if name in {"head", "hair"} and bbox.y <= margin:
            return True
        return False

    def _largest_component(self, mask: np.ndarray) -> np.ndarray:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if count <= 1:
            return mask
        largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        return np.where(labels == largest_label, 255, 0).astype(np.uint8)

    def _confidence_for_part(
        self,
        name: str,
        keypoints: dict[str, PoseKeypoint],
        visible_ratio: float = 0.0,
        status: str = "Visible",
    ) -> float:
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
        pose_score = float(sum(scores) / len(scores)) if scores else 0.15
        visibility_score = min(1.0, max(0.0, visible_ratio * 3.0))
        status_factor = {"Visible": 1.0, "Occluded": 0.55, "Out of Frame": 0.45, "Unknown": 0.30, "Missing": 0.0}.get(status, 0.3)
        return float(max(0.0, min(1.0, (0.65 * pose_score + 0.35 * visibility_score) * status_factor)))

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

    def _detect_small_objects(
        self,
        panel: np.ndarray,
        mask: np.ndarray,
        bbox: BoundingBox,
    ) -> tuple[list[BodyPartLayer], dict[str, object]]:
        parts: list[BodyPartLayer] = []
        metadata: dict[str, object] = {}
        gray = cv2.cvtColor(panel, cv2.COLOR_RGB2GRAY)
        dark = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)[1]

        head_band = np.zeros(mask.shape, dtype=np.uint8)
        y0 = bbox.y
        y1 = min(bbox.y2, bbox.y + max(1, int(bbox.height * 0.25)))
        head_band[y0:y1, bbox.x : bbox.x2] = 255
        head_dark = cv2.bitwise_and(dark, cv2.bitwise_and(mask, head_band))
        if cv2.countNonZero(head_dark) > max(12, bbox.area * 0.004):
            obj_bbox = mask_to_bbox(head_dark)
            parts.append(
                BodyPartLayer(
                    name="accessory",
                    mask=head_dark,
                    bbox=obj_bbox,
                    confidence=0.35,
                    parent="head",
                    status="Visible",
                    metadata={"candidate_type": "glasses_or_hair_accessory"},
                )
            )
            metadata["accessory"] = {
                "status": "Visible",
                "confidence": 0.35,
                "bbox": obj_bbox.to_dict(),
                "layer": "accessory.png",
                "candidate_type": "glasses_or_hair_accessory",
            }

        expanded = bbox.pad(20, panel.shape[1], panel.shape[0])
        outside_character = np.zeros(mask.shape, dtype=np.uint8)
        outside_character[expanded.y : expanded.y2, expanded.x : expanded.x2] = 255
        outside_character = cv2.bitwise_and(outside_character, cv2.bitwise_not(mask))
        edges = cv2.Canny(gray, 80, 180)
        edges = cv2.bitwise_and(edges, outside_character)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=35,
            minLineLength=max(24, min(panel.shape[:2]) // 10),
            maxLineGap=6,
        )
        if lines is not None:
            weapon_mask = np.zeros(mask.shape, dtype=np.uint8)
            for line in lines[:8, 0, :]:
                x1, y1, x2, y2 = [int(v) for v in line]
                cv2.line(weapon_mask, (x1, y1), (x2, y2), 255, 3)
            if cv2.countNonZero(weapon_mask) > 0:
                obj_bbox = mask_to_bbox(weapon_mask)
                parts.append(
                    BodyPartLayer(
                        name="weapon",
                        mask=weapon_mask,
                        bbox=obj_bbox,
                        confidence=0.30,
                        parent="torso",
                        status="Visible",
                        metadata={"candidate_type": "long_edge_object"},
                    )
                )
                metadata["weapon"] = {
                    "status": "Visible",
                    "confidence": 0.30,
                    "bbox": obj_bbox.to_dict(),
                    "layer": "weapon.png",
                    "candidate_type": "long_edge_object",
                }
        return parts, metadata

