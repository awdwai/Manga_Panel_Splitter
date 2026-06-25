"""Benchmark utility API."""

from __future__ import annotations

from pathlib import Path

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.pipeline import MangaAnimatorPipeline


def run_benchmark(input_path: Path, output_dir: Path, config: AppConfig | None = None) -> None:
    """Run the full pipeline and write benchmark reports."""

    app_config = config or AppConfig()
    app_config.output.save_benchmark_markdown = True
    app_config.output.save_performance_json = True
    MangaAnimatorPipeline(app_config).process_path(input_path, output_dir, debug=app_config.output.debug)

