from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.detectors.pose_detector import PoseDetector
from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.segmentation.body_part_splitter import BodyPartSplitter
from MangaAnimatorPrep.types import BoundingBox


def test_unapproved_closeup_does_not_generate_body_parts() -> None:
    mask = np.zeros((180, 180), dtype=np.uint8)
    cv2.ellipse(mask, (90, 70), (45, 55), 0, 0, 360, 255, -1)
    keypoints = PoseDetector(AppConfig())._estimate_geometric(mask, BoundingBox(45, 15, 90, 110))

    parts, metadata = BodyPartSplitter().analyze(mask, keypoints)
    assert parts == []
    assert metadata["approval_required"] is True
    body = metadata["body_parts"]
    assert body["head"]["status"] == "Unknown"
    assert body["left_foot"]["reason"] == "body_part_masks_not_approved"


def test_approved_closeup_exports_only_approved_visible_parts() -> None:
    mask = np.zeros((180, 180), dtype=np.uint8)
    head_mask = np.zeros_like(mask)
    hair_mask = np.zeros_like(mask)
    cv2.ellipse(mask, (90, 70), (45, 55), 0, 0, 360, 255, -1)
    cv2.ellipse(head_mask, (90, 75), (40, 45), 0, 0, 360, 255, -1)
    cv2.ellipse(hair_mask, (90, 35), (38, 20), 0, 0, 360, 255, -1)
    keypoints = PoseDetector(AppConfig())._estimate_geometric(mask, BoundingBox(45, 15, 90, 110))

    parts, metadata = BodyPartSplitter().analyze(
        mask,
        keypoints,
        approved_body_part_masks={"head": head_mask, "hair": hair_mask},
    )
    part_names = {part.name for part in parts}
    assert part_names == {"head", "hair"}
    assert "left_foot" not in part_names
    assert metadata["body_parts"]["left_foot"]["status"] in {"Unknown", "Out of Frame"}

