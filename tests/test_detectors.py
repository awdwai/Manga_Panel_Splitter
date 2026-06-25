from __future__ import annotations

import cv2
import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.detectors.character_detector import CharacterDetector
from MangaAnimatorPrep.detectors.panel_detector import PanelDetector
from MangaAnimatorPrep.detectors.speech_detector import SpeechDetector


def synthetic_page() -> np.ndarray:
    image = np.full((420, 320, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (145, 190), (0, 0, 0), 4)
    cv2.rectangle(image, (170, 20), (300, 190), (0, 0, 0), 4)
    cv2.rectangle(image, (20, 220), (300, 400), (0, 0, 0), 4)
    cv2.circle(image, (85, 85), 24, (30, 30, 30), -1)
    cv2.ellipse(image, (85, 145), (32, 45), 0, 0, 360, (30, 30, 30), -1)
    cv2.ellipse(image, (235, 65), (45, 26), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(image, (235, 65), (45, 26), 0, 0, 360, (0, 0, 0), 2)
    cv2.putText(image, "OK", (222, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    return image


def test_panel_detector_finds_multiple_panels() -> None:
    detections = PanelDetector(AppConfig()).detect(synthetic_page())
    assert len(detections) >= 3
    assert all(det.bbox.area > 0 for det in detections)


def test_character_detector_fallback_finds_character() -> None:
    page = synthetic_page()
    panel = page[20:190, 20:145]
    detections = CharacterDetector(AppConfig()).detect(panel)
    assert detections
    assert detections[0].kind == "character"


def test_speech_detector_finds_bubble() -> None:
    page = synthetic_page()
    panel = page[20:190, 170:300]
    detections = SpeechDetector(AppConfig()).detect(panel)
    assert detections
    assert detections[0].kind == "speech"

