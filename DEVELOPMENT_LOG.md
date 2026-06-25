# Development Log

## Architecture decisions

- Created a modular Python package named `MangaAnimatorPrep`.
- Added typed dataclasses for bounding boxes, detections, pose keypoints, body-part layers, and panel results.
- Centralized runtime selection in `utils/gpu.py`:
  - calls `torch.cuda.is_available()`
  - chooses CUDA when available unless CPU is forced
  - enables mixed precision only on CUDA
  - prefers ONNX Runtime CUDA providers when installed
- Added `ModelCache` to lazily load and reuse heavyweight backends between panels.
- Implemented deterministic OpenCV/Pillow fallbacks for all stages so local tests and sample processing work without large model downloads.
- Kept GroundingDINO, SAM2, LaMa, Stable Diffusion, MediaPipe, and OpenPose integration points behind adapters/lazy imports.

## Manga preprocessing

- Added grayscale normalization, denoising, screentone smoothing, line-art enhancement, adaptive thresholding, and edge enhancement.
- Detectors consume shared preprocessing outputs to avoid duplicated image-processing logic.

## Performance engineering

- Added `PerformanceTracker` for model load time, inference/stage timing, CPU usage samples, VRAM samples, and total processing time per panel.
- Reports are written as `performance_report.json` and `BENCHMARK_RESULTS.md`.
- CUDA memory is sampled through PyTorch when available and unused CUDA cache is released after each panel.

## Reliability decisions

- All heavyweight AI models are optional at runtime; missing packages or checkpoints trigger logged fallbacks instead of crashing the whole pipeline.
- The CLI exits non-zero on processing failure and logs tracebacks.
- Exporters always create the requested animation folder structure for panels and detected characters.

## Bugs/fixes during implementation

- Initial repository had only a placeholder README, so the project was created from scratch on a feature branch.
- The execution environment exposes Python as `python3`; documentation uses `python3` commands.

