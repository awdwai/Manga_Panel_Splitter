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
- Automated tests initially found that speech bubbles could be missed when a white bubble interior merged with a white panel background.
- Added black-outline speech contour detection.
- A second test run showed panel borders could merge with bubble outlines in cropped panels.
- Added removal of border-connected ink components before speech contour detection.

## Verification

- Installed dependencies from `requirements.txt` successfully.
- Created model cache directories with `scripts/download_models.py --verify`.
- Runtime probe confirmed PyTorch is installed; CUDA is not visible in this cloud machine, so CPU fallback was used.
- `python3 -m pytest -q` passed with 5 tests.
- Generated synthetic manga sample data and processed it successfully.
- Generated benchmark reports with per-panel timings, CPU samples, VRAM samples, and model load timings.

## Robustness improvements

- Added multi-character instance handling so panels can export `character_001`, `character_002`, and later instances independently.
- Added overlap/ambiguous-pixel metadata so intersecting masks are preserved and reported instead of silently merged.
- Added partial-body metadata with `Visible`, `Occluded`, `Out of Frame`, and `Unknown` statuses and confidence scores.
- Changed body-part export to skip empty/invented PNGs and record missing anatomy in `metadata.json`.
- Added incomplete-rig support and tests for partial close-ups plus multiple characters in one panel.

