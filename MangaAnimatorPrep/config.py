"""Application configuration for MangaAnimatorPrep."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutionProvider = Literal["auto", "cuda", "cpu"]


class DeviceConfig(BaseModel):
    """GPU/CPU execution preferences."""

    preference: ExecutionProvider = "auto"
    mixed_precision: bool = True
    use_onnx_gpu: bool = True
    gpu_memory_fraction: float = Field(default=0.85, ge=0.1, le=1.0)
    batch_size: int = Field(default=4, ge=1)


class ModelConfig(BaseModel):
    """Optional model checkpoint/config paths."""

    models_dir: Path = Path("MangaAnimatorPrep/models")
    grounding_dino_config: Path | None = None
    grounding_dino_checkpoint: Path | None = None
    sam2_config: Path | None = None
    sam2_checkpoint: Path | None = None
    lama_checkpoint: Path | None = None
    stable_diffusion_model: str | None = None
    openpose_model_dir: Path | None = None


class PreprocessingConfig(BaseModel):
    """Manga-specific preprocessing switches."""

    grayscale_normalization: bool = True
    screentone_removal: bool = True
    line_art_enhancement: bool = True
    adaptive_thresholding: bool = True
    denoise: bool = True
    edge_enhancement: bool = True


class OutputConfig(BaseModel):
    """Output and debugging settings."""

    debug: bool = False
    save_performance_json: bool = True
    save_benchmark_markdown: bool = True
    transparent_layers: bool = True


class WorkflowConfig(BaseModel):
    """Human-in-the-loop workflow controls."""

    auto_detect_panels: bool = True
    expected_panels: int | None = Field(default=None, ge=1, le=20)
    expected_characters: int | None = Field(default=None, ge=1, le=10)
    require_user_approval: bool = True
    approved_character_masks: bool = False
    approved_body_part_masks: bool = False
    body_part_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)


class AppConfig(BaseModel):
    """Top-level application config."""

    device: DeviceConfig = Field(default_factory=DeviceConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    min_panel_area_ratio: float = Field(default=0.015, ge=0.0, le=1.0)
    min_character_area_ratio: float = Field(default=0.02, ge=0.0, le=1.0)
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)

    @classmethod
    def from_file(cls, path: Path | str | None) -> "AppConfig":
        if path is None:
            return cls.from_environment()
        config_path = Path(path)
        data = json.loads(config_path.read_text(encoding="utf-8"))
        base = cls.from_environment()
        merged = _deep_merge(base.to_json_dict(), data)
        return cls.model_validate(merged)

    @classmethod
    def from_environment(cls) -> "AppConfig":
        config = cls()
        env_models_dir = os.getenv("MANGA_ANIMATOR_MODELS_DIR")
        if env_models_dir:
            config.models.models_dir = Path(env_models_dir)
        if os.getenv("MANGA_ANIMATOR_FORCE_CPU") == "1":
            config.device.preference = "cpu"
        if os.getenv("MANGA_ANIMATOR_FORCE_CUDA") == "1":
            config.device.preference = "cuda"
        if os.getenv("MANGA_ANIMATOR_DEBUG") == "1":
            config.output.debug = True
        batch_size = os.getenv("MANGA_ANIMATOR_BATCH_SIZE")
        if batch_size:
            config.device.batch_size = max(1, int(batch_size))
        return config

    def to_json_dict(self) -> dict[str, Any]:
        return json.loads(self.model_dump_json())


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load application config from a JSON file and environment overrides."""

    return AppConfig.from_file(path)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge nested config dictionaries while preserving Pydantic validation."""

    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

