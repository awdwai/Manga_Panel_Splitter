from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.interactive_segmentation import InteractiveSegmentationSession


def test_click_to_segment_creates_independent_layers() -> None:
    image = np.full((160, 220, 3), 255, dtype=np.uint8)
    cv2.circle(image, (60, 60), 28, (20, 20, 20), -1)
    cv2.rectangle(image, (140, 40), (190, 100), (80, 80, 80), -1)
    session = InteractiveSegmentationSession(image)

    first = session.new_layer_from_click(60, 60)
    session.active_layer_id = None
    second = session.new_layer_from_click(165, 70)

    assert first.layer_id != second.layer_id
    assert len(session.layers) == 2
    assert cv2.countNonZero(first.mask) > 0
    assert cv2.countNonZero(second.mask) > 0


def test_positive_negative_prompts_refine_mask() -> None:
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    cv2.circle(image, (60, 60), 35, (30, 30, 30), -1)
    session = InteractiveSegmentationSession(image)
    layer = session.new_layer_from_click(60, 60)
    before = cv2.countNonZero(layer.mask)

    session.add_prompt(60, 60, positive=False)
    after = cv2.countNonZero(session.active_layer.mask)

    assert after < before


def test_mask_editing_tools_update_active_layer() -> None:
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    cv2.circle(image, (40, 40), 12, (30, 30, 30), -1)
    session = InteractiveSegmentationSession(image)
    layer = session.new_layer_from_click(40, 40)
    before = cv2.countNonZero(layer.mask)

    session.brush(80, 80, 10, erase=False)
    brushed = cv2.countNonZero(session.active_layer.mask)
    session.contract_active(2)
    contracted = cv2.countNonZero(session.active_layer.mask)

    assert brushed > before
    assert contracted < brushed

