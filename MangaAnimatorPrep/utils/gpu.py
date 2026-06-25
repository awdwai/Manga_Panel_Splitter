"""GPU, CUDA, mixed precision, and ONNX Runtime helpers."""

from __future__ import annotations

import contextlib
import importlib
import logging
from dataclasses import dataclass
from typing import Iterator

from MangaAnimatorPrep.config import DeviceConfig

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeInfo:
    """Resolved runtime capabilities."""

    device: str
    cuda_available: bool
    mixed_precision: bool
    torch_available: bool
    onnx_providers: list[str]
    gpu_name: str | None = None
    total_vram_mb: float | None = None


def _import_torch() -> object | None:
    try:
        return importlib.import_module("torch")
    except Exception as exc:  # pragma: no cover - depends on environment
        LOGGER.info("PyTorch unavailable: %s", exc)
        return None


def torch_cuda_available() -> bool:
    """Return torch.cuda.is_available() when PyTorch is importable."""

    torch = _import_torch()
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception as exc:  # pragma: no cover - defensive for broken installs
        LOGGER.warning("torch.cuda.is_available() failed: %s", exc)
        return False


def get_onnx_providers(prefer_gpu: bool = True) -> list[str]:
    """Resolve ONNX Runtime providers with CUDA first when available."""

    try:
        ort = importlib.import_module("onnxruntime")
    except Exception as exc:  # pragma: no cover - optional dependency
        LOGGER.info("ONNX Runtime unavailable: %s", exc)
        return []
    available = list(ort.get_available_providers())
    if prefer_gpu and "CUDAExecutionProvider" in available:
        providers = ["CUDAExecutionProvider"]
        if "CPUExecutionProvider" in available:
            providers.append("CPUExecutionProvider")
        return providers
    return ["CPUExecutionProvider"] if "CPUExecutionProvider" in available else available


def resolve_runtime(device_config: DeviceConfig) -> RuntimeInfo:
    """Resolve the best execution device according to config and installed libraries."""

    torch = _import_torch()
    cuda_available = False
    gpu_name: str | None = None
    total_vram_mb: float | None = None
    if torch is not None:
        try:
            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                gpu_name = str(torch.cuda.get_device_name(0))
                props = torch.cuda.get_device_properties(0)
                total_vram_mb = float(props.total_memory / (1024 * 1024))
        except Exception as exc:  # pragma: no cover - driver dependent
            LOGGER.warning("CUDA probing failed: %s", exc)
            cuda_available = False

    if device_config.preference == "cpu":
        device = "cpu"
    elif device_config.preference == "cuda":
        device = "cuda" if cuda_available else "cpu"
        if not cuda_available:
            LOGGER.warning("CUDA was requested but is unavailable; falling back to CPU")
    else:
        device = "cuda" if cuda_available else "cpu"

    return RuntimeInfo(
        device=device,
        cuda_available=cuda_available,
        mixed_precision=bool(device == "cuda" and device_config.mixed_precision),
        torch_available=torch is not None,
        onnx_providers=get_onnx_providers(device_config.use_onnx_gpu),
        gpu_name=gpu_name,
        total_vram_mb=total_vram_mb,
    )


@contextlib.contextmanager
def inference_context(runtime: RuntimeInfo) -> Iterator[None]:
    """Wrap PyTorch inference with no-grad and autocast when CUDA FP16 is active."""

    torch = _import_torch()
    if torch is None:
        yield
        return
    with torch.no_grad():
        if runtime.mixed_precision and runtime.device == "cuda":
            with torch.cuda.amp.autocast(dtype=torch.float16):
                yield
        else:
            yield


def empty_cuda_cache() -> None:
    """Release unused CUDA cache if PyTorch/CUDA are available."""

    torch = _import_torch()
    if torch is not None:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover - non-critical cleanup
            LOGGER.debug("Unable to empty CUDA cache", exc_info=True)


def current_vram_mb() -> float:
    """Return currently allocated CUDA memory in MB."""

    torch = _import_torch()
    if torch is None:
        return 0.0
    try:
        if torch.cuda.is_available():
            return float(torch.cuda.memory_allocated() / (1024 * 1024))
    except Exception:  # pragma: no cover
        LOGGER.debug("Unable to read CUDA memory", exc_info=True)
    return 0.0

