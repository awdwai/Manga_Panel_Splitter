"""Performance measurement and report generation."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

import psutil

from MangaAnimatorPrep.utils.gpu import RuntimeInfo, current_vram_mb


@dataclass(slots=True)
class MetricRecord:
    """One timed metric record."""

    name: str
    seconds: float
    cpu_percent: float
    vram_mb: float
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class PanelMetrics:
    """Aggregated metrics for one processed panel."""

    panel_id: str
    model_load_seconds: dict[str, float] = field(default_factory=dict)
    inference_seconds: dict[str, float] = field(default_factory=dict)
    records: list[MetricRecord] = field(default_factory=list)
    total_seconds: float = 0.0
    peak_vram_mb: float = 0.0
    peak_cpu_percent: float = 0.0


class PerformanceTracker:
    """Collect timings, CPU usage, and CUDA memory snapshots."""

    def __init__(self, runtime: RuntimeInfo) -> None:
        self.runtime = runtime
        self._process = psutil.Process()
        self.records: list[MetricRecord] = []

    @contextmanager
    def measure(self, name: str, **metadata: object) -> Iterator[None]:
        self._process.cpu_percent(interval=None)
        start_vram = current_vram_mb()
        start = time.perf_counter()
        try:
            yield
        finally:
            seconds = time.perf_counter() - start
            cpu = float(self._process.cpu_percent(interval=None))
            vram = max(start_vram, current_vram_mb())
            self.records.append(
                MetricRecord(name=name, seconds=seconds, cpu_percent=cpu, vram_mb=vram, metadata=metadata)
            )

    def build_panel_metrics(
        self,
        panel_id: str,
        model_load_seconds: dict[str, float],
        start_index: int,
    ) -> PanelMetrics:
        records = self.records[start_index:]
        inference_seconds: dict[str, float] = {}
        for record in records:
            inference_seconds[record.name] = inference_seconds.get(record.name, 0.0) + record.seconds
        return PanelMetrics(
            panel_id=panel_id,
            model_load_seconds=model_load_seconds,
            inference_seconds=inference_seconds,
            records=records,
            total_seconds=sum(record.seconds for record in records),
            peak_vram_mb=max((record.vram_mb for record in records), default=0.0),
            peak_cpu_percent=max((record.cpu_percent for record in records), default=0.0),
        )


def write_performance_report(path: Path, metrics: list[PanelMetrics], runtime: RuntimeInfo) -> None:
    """Write JSON performance report."""

    payload = {
        "runtime": {
            "device": runtime.device,
            "cuda_available": runtime.cuda_available,
            "mixed_precision": runtime.mixed_precision,
            "torch_available": runtime.torch_available,
            "onnx_providers": runtime.onnx_providers,
            "gpu_name": runtime.gpu_name,
            "total_vram_mb": runtime.total_vram_mb,
        },
        "panels": [asdict(metric) for metric in metrics],
        "summary": summarize_metrics(metrics),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def summarize_metrics(metrics: list[PanelMetrics]) -> dict[str, float | int]:
    """Create aggregate performance summary."""

    total = sum(metric.total_seconds for metric in metrics)
    count = len(metrics)
    return {
        "panel_count": count,
        "total_processing_seconds": total,
        "average_seconds_per_panel": total / count if count else 0.0,
        "peak_vram_mb": max((metric.peak_vram_mb for metric in metrics), default=0.0),
        "peak_cpu_percent": max((metric.peak_cpu_percent for metric in metrics), default=0.0),
    }


def write_benchmark_markdown(path: Path, metrics: list[PanelMetrics], runtime: RuntimeInfo) -> None:
    """Write human-readable benchmark report."""

    summary = summarize_metrics(metrics)
    lines = [
        "# Benchmark Results",
        "",
        f"- Device: `{runtime.device}`",
        f"- CUDA available: `{runtime.cuda_available}`",
        f"- Mixed precision: `{runtime.mixed_precision}`",
        f"- GPU: `{runtime.gpu_name or 'not detected'}`",
        f"- ONNX providers: `{', '.join(runtime.onnx_providers) or 'none'}`",
        f"- Panels processed: `{summary['panel_count']}`",
        f"- Total processing time: `{summary['total_processing_seconds']:.4f}s`",
        f"- Average time per panel: `{summary['average_seconds_per_panel']:.4f}s`",
        f"- Peak VRAM usage: `{summary['peak_vram_mb']:.2f} MB`",
        f"- Peak CPU usage sample: `{summary['peak_cpu_percent']:.2f}%`",
        "",
        "| Panel | Total (s) | Peak VRAM (MB) | Peak CPU (%) | Main stages |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in metrics:
        stages = ", ".join(f"{key}={value:.3f}s" for key, value in metric.inference_seconds.items())
        lines.append(
            f"| {metric.panel_id} | {metric.total_seconds:.4f} | {metric.peak_vram_mb:.2f} | "
            f"{metric.peak_cpu_percent:.2f} | {stages} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

