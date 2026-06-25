from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.detectors.pose_detector import PoseDetector
from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.segmentation.body_part_splitter import BodyPartSplitter
from MangaAnimatorPrep.types import BoundingBox


def test_partial_closeup_does_not_export_legs() -> None:
    mask = np.zeros((180, 180), dtype=np.uint8)
    cv2.ellipse(mask, (90, 70), (45, 55), 0, 0, 360, 255, -1)
    keypoints = PoseDetector(AppConfig())._estimate_geometric(mask, BoundingBox(45, 15, 90, 110))

    parts, metadata = BodyPartSplitter().analyze(mask, keypoints)
    part_names = {part.name for part in parts}
    assert "head" in part_names
    assert "left_foot" not in part_names
    assert "right_foot" not in part_names
    body = metadata["body_parts"]
    assert body["left_foot"]["status"] in {"Out of Frame", "Unknown", "Occluded"}
    assert body["right_foot"]["status"] in {"Out of Frame", "Unknown", "Occluded"}

