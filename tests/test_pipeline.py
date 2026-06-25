from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.pipeline import MangaAnimatorPipeline
from scripts.create_sample_data import create_sample


def test_pipeline_processes_sample_page(tmp_path: Path) -> None:
    sample = tmp_path / "sample.png"
    output = tmp_path / "output"
    create_sample(sample)

    config = AppConfig()
    config.output.debug = True
    results = MangaAnimatorPipeline(config).process_path(sample, output, debug=True)

    assert len(results) >= 1
    panel_dir = output / "panel_001"
    assert panel_dir.exists()
    assert (panel_dir / "panel_001.png").exists()
    assert (panel_dir / "background.png").exists()
    assert (panel_dir / "debug").exists()
    assert (output / "performance_report.json").exists()
    assert (output / "BENCHMARK_RESULTS.md").exists()

    report = json.loads((output / "performance_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["panel_count"] == len(results)
    character_dirs = sorted(panel_dir.glob("character_*"))
    assert character_dirs
    assert (character_dirs[0] / "character.png").exists()
    assert (character_dirs[0] / "rig.json").exists()
    assert (character_dirs[0] / "metadata.json").exists()
    metadata = json.loads((character_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["character_id"] == "character_001"
    assert "visible_body_parts" in metadata["body"]
    assert "missing_body_parts" in metadata["body"]
    assert metadata["workflow"]["body_part_masks_approved"] is False
    assert metadata["body"]["approval_required"] is True
    assert not (character_dirs[0] / "left_foot.png").exists()


def test_pipeline_exports_multiple_characters_independently(tmp_path: Path) -> None:
    sample = tmp_path / "multi.png"
    output = tmp_path / "output_multi"
    image = np.full((360, 520, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (15, 15), (505, 345), (0, 0, 0), 4)
    for cx in (170, 350):
        cv2.circle(image, (cx, 100), 32, (20, 20, 20), -1)
        cv2.ellipse(image, (cx, 205), (46, 88), 0, 0, 360, (35, 35, 35), -1)
        cv2.line(image, (cx - 42, 190), (cx - 75, 265), (35, 35, 35), 8)
        cv2.line(image, (cx + 42, 190), (cx + 75, 265), (35, 35, 35), 8)
    Image.fromarray(image).save(sample)

    config = AppConfig()
    config.min_character_area_ratio = 0.01
    results = MangaAnimatorPipeline(config).process_path(sample, output, debug=True)

    assert results
    character_dirs = sorted((output / "panel_001").glob("character_*"))
    assert len(character_dirs) >= 2
    assert character_dirs[0].name == "character_001"
    assert character_dirs[1].name == "character_002"
    for char_dir in character_dirs[:2]:
        metadata = json.loads((char_dir / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["character_id"] == char_dir.name
        assert metadata["mask"]["total_pixels"] > 0
        assert (char_dir / "character.png").exists()


