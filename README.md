# MangaAnimatorPrep

MangaAnimatorPrep is a local desktop/CLI preparation pipeline for manga animation workflows.
It accepts manga pages or single panels and exports animation-ready assets:

- detected panel crops
- character masks and transparent character layers
- speech/text/effects layers
- reconstructed backgrounds
- pose estimates
- body-part layers
- rig metadata
- debug visualizations
- performance reports

The implementation is optimized for NVIDIA GPUs when available. It detects CUDA with
`torch.cuda.is_available()`, uses FP16 inference where supported, prefers ONNX Runtime CUDA
providers when available, caches models after first load, and falls back to CPU-safe OpenCV
heuristics when heavyweight models or CUDA are unavailable.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/download_models.py --models-dir MangaAnimatorPrep/models
python3 -m MangaAnimatorPrep.main process sample_data --output output --debug
python3 -m MangaAnimatorPrep.main benchmark sample_data --output output
python3 -m MangaAnimatorPrep.main gui
python3 -m pytest -q
```

On Windows 11 with an RTX 5060, install a CUDA-enabled PyTorch build that matches your
driver/CUDA runtime before running the application. The app will automatically use CUDA and
mixed precision if PyTorch reports CUDA availability.

## Local GUI launch on Windows

From the repository root, use one of:

```bat
run.bat
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Both scripts activate `.venv` when present, verify dependencies, and launch the PySide6 GUI.

## Development executable build on Windows

From the repository root:

```bat
dev_build.bat
```

This uses PyInstaller to build and smoke-launch:

```text
dist\MangaAnimatorPrep.exe
```

## CLI

```bash
python3 -m MangaAnimatorPrep.main process <input-file-or-directory> --output output --debug
python3 -m MangaAnimatorPrep.main benchmark <input-file-or-directory> --output output
python3 -m MangaAnimatorPrep.main gui
python3 -m MangaAnimatorPrep.main gui --smoke-test
python3 -m MangaAnimatorPrep.main gui --smoke-test --smoke-input sample_data/sample_page.png --smoke-output gui_smoke_output
python3 -m MangaAnimatorPrep.main system-info
```

The desktop GUI is implemented with PySide6. In headless CI/cloud environments, use Qt's
offscreen platform for smoke tests:

```bash
QT_QPA_PLATFORM=offscreen python3 -m MangaAnimatorPrep.main gui --smoke-test
```

Linux systems may also need Qt's EGL runtime library:

```bash
sudo apt-get install libegl1
```

## Review-first workflow

The GUI follows a review-first workflow:

1. Import image.
2. Detect panels/characters with the Panel Detection controls.
3. Review/edit overlays and approve panel/character masks.
4. Continue export.

Body-part PNGs are not generated from geometric slicing. If approved semantic/correction body-part
masks are not available, the app exports `character.png`, `metadata.json`, and an incomplete
`rig.json` with `body_part_masks_not_approved` statuses instead of fabricating anatomy.

## Body-part review table

The GUI uses a table-based review workflow for speed:

- sortable/searchable/filterable body-part table
- columns for part name, status, confidence, visible state, bounding box, and action
- selecting a row highlights and centers that part in the image viewer
- Edit/Create opens a movable bounding box with corner handles and numeric controls
- Snap to Edges adjusts the selected boundary to nearby detected edges
- Auto Resegment updates only the selected body-part layer inside the edited box
- fixed bottom toolbar keeps Previous, Redo Detection, Accept, Next, Export, and Cancel visible while scrolling

## Output structure

```text
output/
  BENCHMARK_RESULTS.md
  performance_report.json
  panel_001/
    panel_001.png
    background.png
    rig.json
    debug/
      panel_outline.png
      pose_overlay.png
      character_mask.png
    speech/
    effects/
    character_001/
      character.png
      metadata.json
      head.png
      hair.png
      torso.png
      left_upper_arm.png
      left_lower_arm.png
      left_hand.png
      right_upper_arm.png
      right_lower_arm.png
      right_hand.png
      left_upper_leg.png
      left_lower_leg.png
      left_foot.png
      right_upper_leg.png
      right_lower_leg.png
      right_foot.png
```

## Architecture

The pipeline is modular and can run with either production model backends or deterministic
fallbacks:

- `detectors/`: panel, character, speech, text, effects, and pose detection
- `segmentation/`: SAM2-aware character segmentation and geometry body-part splitting
- `inpainting/`: LaMa-aware background reconstruction with OpenCV/Stable Diffusion fallbacks
- `exporters/`: animation layer and rig JSON export
- `utils/`: image preprocessing, GPU/ONNX detection, model cache, file utilities, benchmarks

Heavyweight models are loaded lazily and cached through a shared model cache. Panels are processed
in batches where this is beneficial for lightweight detectors, and model instances are never
reloaded between panels within a process.

## Notes on optional AI backends

The repository includes robust CPU fallbacks so tests and sample processing can run without large
model files. For production quality extraction, place/download compatible checkpoints into
`MangaAnimatorPrep/models` and configure paths with environment variables or a JSON config file:

- GroundingDINO for open-vocabulary character detection
- SAM2 for segmentation
- LaMa for inpainting
- Stable Diffusion inpainting as a secondary background fallback
- MediaPipe Pose with OpenPose-style geometric fallback

See `scripts/download_models.py` for model source hints and cache directory setup.
