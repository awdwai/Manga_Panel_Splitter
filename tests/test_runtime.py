from __future__ import annotations

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.utils.gpu import resolve_runtime, torch_cuda_available


def test_runtime_resolution_is_safe() -> None:
    config = AppConfig()
    runtime = resolve_runtime(config.device)
    assert runtime.device in {"cpu", "cuda"}
    assert isinstance(torch_cuda_available(), bool)
    if runtime.device == "cpu":
        assert runtime.mixed_precision is False

