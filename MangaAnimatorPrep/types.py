"""Shared typed records used across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np


DetectionKind = Literal["panel", "character", "speech", "text", "effect"]


@dataclass(slots=True)
class BoundingBox:
    """Axis-aligned bounding box in image coordinates."""

    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def clamp(self, image_width: int, image_height: int) -> "BoundingBox":
        x = max(0, min(self.x, image_width - 1))
        y = max(0, min(self.y, image_height - 1))
        x2 = max(x + 1, min(self.x2, image_width))
        y2 = max(y + 1, min(self.y2, image_height))
        return BoundingBox(x=x, y=y, width=x2 - x, height=y2 - y)

    def pad(self, pixels: int, image_width: int, image_height: int) -> "BoundingBox":
        return BoundingBox(
            x=self.x - pixels,
            y=self.y - pixels,
            width=self.width + 2 * pixels,
            height=self.height + 2 * pixels,
        ).clamp(image_width, image_height)

    def to_xyxy(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x2, self.y2)

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(slots=True)
class Detection:
    """Detection result with an optional mask and contour."""

    kind: DetectionKind
    bbox: BoundingBox
    confidence: float
    mask: np.ndarray | None = None
    label: str | None = None
    contour: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PoseKeypoint:
    """Pose keypoint coordinate and confidence."""

    name: str
    x: float
    y: float
    confidence: float

    def to_dict(self) -> dict[str, float | str]:
        return {"name": self.name, "x": self.x, "y": self.y, "confidence": self.confidence}


@dataclass(slots=True)
class BodyPartLayer:
    """Body-part mask/layer with confidence metadata."""

    name: str
    mask: np.ndarray
    bbox: BoundingBox
    confidence: float
    parent: str | None = None
    pivot: tuple[float, float] | None = None
    status: str = "Visible"
    ambiguous_pixels: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PanelResult:
    """All exported data for one panel."""

    panel_index: int
    panel_path: Path
    output_dir: Path
    detections: list[Detection]
    metrics: dict[str, Any]

