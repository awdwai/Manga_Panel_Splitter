"""Command-line interface for MangaAnimatorPrep."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from MangaAnimatorPrep.config import load_config
from MangaAnimatorPrep.pipeline import MangaAnimatorPipeline
from MangaAnimatorPrep.utils.gpu import resolve_runtime, torch_cuda_available

LOGGER = logging.getLogger(__name__)
CONSOLE = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare manga pages/panels for animation workflows.")
    parser.add_argument("--config", type=Path, default=None, help="Optional JSON config path.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    subparsers = parser.add_subparsers(dest="command", required=True)

    process = subparsers.add_parser("process", help="Process image(s) and export animation-ready assets.")
    process.add_argument("input", type=Path, help="Input image or directory containing JPG/PNG/WEBP files.")
    process.add_argument("--output", type=Path, default=Path("output"), help="Output directory.")
    process.add_argument("--debug", action="store_true", help="Write debug visualizations.")

    benchmark = subparsers.add_parser("benchmark", help="Run processing and generate benchmark reports.")
    benchmark.add_argument("input", type=Path, help="Input image or directory.")
    benchmark.add_argument("--output", type=Path, default=Path("output"), help="Output directory.")
    benchmark.add_argument("--debug", action="store_true", help="Write debug visualizations.")

    gui = subparsers.add_parser("gui", help="Launch the desktop GUI.")
    gui.add_argument("--smoke-test", action="store_true", help="Validate PySide6 GUI launch without entering mainloop.")
    gui.add_argument("--smoke-input", type=Path, default=None, help="Optional image/folder to load during GUI smoke test.")
    gui.add_argument("--smoke-output", type=Path, default=None, help="Optional output folder to process during GUI smoke test.")

    subparsers.add_parser("system-info", help="Print runtime GPU/ONNX/PyTorch capability information.")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def print_system_info(config_path: Path | None) -> None:
    config = load_config(config_path)
    runtime = resolve_runtime(config.device)
    table = Table(title="MangaAnimatorPrep Runtime")
    table.add_column("Capability")
    table.add_column("Value")
    table.add_row("Device", runtime.device)
    table.add_row("torch.cuda.is_available()", str(torch_cuda_available()))
    table.add_row("Mixed precision", str(runtime.mixed_precision))
    table.add_row("PyTorch available", str(runtime.torch_available))
    table.add_row("GPU", runtime.gpu_name or "not detected")
    table.add_row("Total VRAM MB", f"{runtime.total_vram_mb:.2f}" if runtime.total_vram_mb else "unknown")
    table.add_row("ONNX providers", ", ".join(runtime.onnx_providers) or "none")
    CONSOLE.print(table)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if args.command == "system-info":
        print_system_info(args.config)
        return 0

    if args.command == "gui":
        from MangaAnimatorPrep.gui import gui_smoke_test, launch_gui

        if args.smoke_test:
            result = gui_smoke_test(args.smoke_input, args.smoke_output)
            CONSOLE.print(result)
            return 0 if result["status"] == "working" else 1
        launch_gui(args.config)
        return 0

    config = load_config(args.config)
    config.output.debug = bool(args.debug)
    if args.command == "benchmark":
        config.output.save_benchmark_markdown = True
        config.output.save_performance_json = True

    pipeline = MangaAnimatorPipeline(config)
    try:
        results = pipeline.process_path(args.input, args.output, debug=args.debug)
    except Exception as exc:
        LOGGER.exception("Processing failed")
        CONSOLE.print(f"[red]Processing failed:[/red] {exc}")
        return 1
    CONSOLE.print(f"[green]Processed {len(results)} panel(s). Output:[/green] {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

