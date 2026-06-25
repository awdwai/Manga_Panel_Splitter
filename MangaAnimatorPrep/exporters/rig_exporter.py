"""Rig JSON export."""

from __future__ import annotations

import json
from pathlib import Path

from MangaAnimatorPrep.types import BodyPartLayer, PoseKeypoint


class RigExporter:
    """Export body part hierarchy, pivots, bboxes, and confidence scores."""

    def export(self, path: Path, body_parts: list[BodyPartLayer], keypoints: list[PoseKeypoint]) -> None:
        payload = {
            "schema_version": "1.0",
            "keypoints": [keypoint.to_dict() for keypoint in keypoints],
            "body_parts": [
                {
                    "name": part.name,
                    "parent": part.parent,
                    "bbox": part.bbox.to_dict(),
                    "pivot": {"x": part.pivot[0], "y": part.pivot[1]} if part.pivot else None,
                    "confidence": part.confidence,
                    "layer": f"{part.name}.png",
                }
                for part in body_parts
            ],
            "hierarchy": {
                part.name: {"parent": part.parent, "children": [child.name for child in body_parts if child.parent == part.name]}
                for part in body_parts
            },
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

