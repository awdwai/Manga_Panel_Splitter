"""Human-in-the-loop detection workflow helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.detectors.character_detector import CharacterDetector
from MangaAnimatorPrep.detectors.panel_detector import PanelDetector
from MangaAnimatorPrep.types import Detection
from MangaAnimatorPrep.utils.image_utils import crop_with_bbox, load_image


@dataclass(slots=True)
class PanelDraft:
    panel_id: str
    detection: Detection
    characters: list[Detection] = field(default_factory=list)
    approved: bool = False
    expected_characters: int | None = None


@dataclass(slots=True)
class DetectionSession:
    image_path: Path
    panels: list[PanelDraft]
    approved_panels: bool = False
    approved_characters: bool = False

    @property
    def low_confidence_items(self) -> list[str]:
        items: list[str] = []
        for panel in self.panels:
            if panel.detection.confidence < 0.80:
                items.append(panel.panel_id)
            for index, character in enumerate(panel.characters, start=1):
                if character.confidence < 0.80:
                    items.append(f"{panel.panel_id}/character_{index:03d}")
        return items


class DetectionWorkflow:
    """Run detection stages without exporting body parts."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.panel_detector = PanelDetector(config)
        self.character_detector = CharacterDetector(config)

    def detect(self, image_path: Path) -> DetectionSession:
        image = load_image(image_path)
        panel_detections = self._detect_panels(image)
        panels: list[PanelDraft] = []
        for index, panel_detection in enumerate(panel_detections, start=1):
            panel = crop_with_bbox(image, panel_detection.bbox)
            characters = self.character_detector.detect(panel)
            characters = self._fit_expected_characters(panel, characters, self.config.workflow.expected_characters)
            panels.append(
                PanelDraft(
                    panel_id=f"panel_{index:03d}",
                    detection=panel_detection,
                    characters=characters,
                    expected_characters=self.config.workflow.expected_characters,
                )
            )
        return DetectionSession(image_path=image_path, panels=panels)

    def _detect_panels(self, image: np.ndarray) -> list[Detection]:
        if not self.config.workflow.auto_detect_panels:
            height, width = image.shape[:2]
            from MangaAnimatorPrep.types import BoundingBox

            mask = np.full((height, width), 255, dtype=np.uint8)
            return [Detection("panel", BoundingBox(0, 0, width, height), 1.0, mask=mask, label="manual_full_image")]
        panels = self.panel_detector.detect(image)
        expected = self.config.workflow.expected_panels
        if expected is not None:
            panels = sorted(panels, key=lambda item: item.confidence, reverse=True)[:expected]
        return panels

    def _fit_expected_characters(
        self,
        panel: np.ndarray,
        characters: list[Detection],
        expected: int | None,
    ) -> list[Detection]:
        if expected is None or len(characters) == expected:
            return characters
        if len(characters) > expected:
            return sorted(characters, key=lambda item: item.confidence, reverse=True)[:expected]
        # If the detector under-counts, return current detections and let the GUI request
        # manual user clicks/masks rather than fabricating characters.
        return characters

