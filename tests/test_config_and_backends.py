from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from MangaAnimatorPrep.config import AppConfig, load_config
from MangaAnimatorPrep.detectors.character_detector import CharacterDetector
from MangaAnimatorPrep.inpainting.lama_inpainter import LaMaInpainter
from MangaAnimatorPrep.segmentation.sam_segmenter import SAMSegmenter
from MangaAnimatorPrep.types import BoundingBox, Detection


def test_nested_config_file_is_validated(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"device": {"preference": "cpu"}, "output": {"debug": True}}), encoding="utf-8")
    config = load_config(config_path)
    assert config.device.preference == "cpu"
    assert config.output.debug is True
    assert config.device.batch_size == AppConfig().device.batch_size


def test_optional_character_backend_load_failure_falls_back(tmp_path: Path) -> None:
    config = AppConfig()
    config.models.grounding_dino_config = tmp_path / "missing.py"
    config.models.grounding_dino_checkpoint = tmp_path / "missing.pth"
    panel = np.full((120, 120, 3), 255, dtype=np.uint8)
    detections = CharacterDetector(config).detect(panel)
    assert detections


def test_optional_sam_backend_load_failure_falls_back(tmp_path: Path) -> None:
    config = AppConfig()
    config.models.sam2_config = tmp_path / "missing.yaml"
    config.models.sam2_checkpoint = tmp_path / "missing.pt"
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    detection = Detection("character", BoundingBox(20, 20, 60, 80), 0.5)
    mask = SAMSegmenter(config).segment(image, detection)
    assert mask.shape == image.shape[:2]


def test_optional_lama_backend_load_failure_falls_back(tmp_path: Path) -> None:
    config = AppConfig()
    config.models.lama_checkpoint = tmp_path / "missing"
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    mask = np.zeros((120, 120), dtype=np.uint8)
    mask[40:80, 40:80] = 255
    result = LaMaInpainter(config).inpaint(image, mask)
    assert result.shape == image.shape

