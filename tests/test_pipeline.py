from __future__ import annotations

import json
from pathlib import Path

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

