# MangaAnimatorPrep Implementation Audit

Audit date: 2026-06-25

This audit evaluates the actual implementation in the repository, not the intended architecture.
The current project has a runnable OpenCV/PySide6-based pipeline, but most named deep-learning
models are optional hooks or fallbacks rather than installed, exercised production integrations.

## Installed backend reality check

Command used:

```bash
python3 - <<'PY'
import importlib.util
packages = ['torch','onnxruntime','mediapipe','groundingdino','sam2','saicinpainting','PySide6','tkinter']
for pkg in packages:
    spec = importlib.util.find_spec(pkg)
    print(f'{pkg}: {"installed" if spec else "missing"}')
if importlib.util.find_spec('torch'):
    import torch
    print(f'torch.cuda.is_available(): {torch.cuda.is_available()}')
    print(f'torch.version.cuda: {getattr(torch.version, "cuda", None)}')
PY
```

Observed result:

```text
torch: installed
onnxruntime: installed
mediapipe: missing
groundingdino: missing
sam2: missing
saicinpainting: missing
PySide6: installed after GUI migration
tkinter: no longer used by the application GUI
torch.cuda.is_available(): False
torch.version.cuda: 13.0
```

`requirements.txt` contains `torch`, `torchvision`, and `onnxruntime-gpu`, but does **not** contain
MediaPipe, GroundingDINO, SAM2, LaMa/saicinpainting, OpenPose, or Stable Diffusion/diffusers.

## Module classification

| Module / Feature | Classification | Evidence |
|---|---|---|
| Panel detection | **PARTIAL** | Implemented with OpenCV heuristics, not a trained model. `detectors/panel_detector.py` uses `cv2.findContours` on Canny/morphology outputs and white-region candidates. It can detect synthetic rectangular panels and some borderless regions, but irregular/overlapping/borderless production manga panels are heuristic-only. |
| Character detection | **PARTIAL** | Real code exists, but default path is OpenCV fallback. `detectors/character_detector.py` tries `groundingdino.util.inference` only if checkpoint paths are configured; GroundingDINO is not installed. Fallback uses thresholding, morphology, contours, and a central ellipse fallback. |
| Speech detection | **PARTIAL** | Real OpenCV implementation exists in `detectors/speech_detector.py`, using dark outline contours, light-region contours, connected-component border filtering, and bbox heuristics. It is not an AI speech-bubble detector and may fail on complex manga. |
| Text detection | **PARTIAL** | Real OpenCV implementation exists in `detectors/text_detector.py`, using thresholding, morphology, and contours. It does not run OCR or a trained text detector; it creates approximate text-region masks. |
| Effect detection | **PARTIAL** | Real OpenCV implementation exists in `detectors/effect_detector.py`, using `cv2.HoughLinesP` for speed/motion lines. It is heuristic and does not classify energy/impact effects with an AI model. |
| Segmentation | **PARTIAL / PLACEHOLDER AI** | `segmentation/sam_segmenter.py` contains a SAM2 adapter hook, but SAM2 is not installed and no checkpoint is present. The actual working path is `_fallback_segment`, which uses grayscale thresholding, bbox masks, morphology, and blur. This is real image processing, but not real AI segmentation. |
| Pose estimation | **PARTIAL / PLACEHOLDER AI** | `detectors/pose_detector.py` attempts to import MediaPipe, but MediaPipe is not installed. The actual working path is `_estimate_geometric`, which generates keypoints from bounding-box/mask proportions. This is not real pose estimation in the current environment. |
| Body-part splitting | **PARTIAL** | `segmentation/body_part_splitter.py` does create separate named masks for head, hair, torso, arms, hands, legs, and feet. However, `_geometric_regions` defines fixed rectangular regions over the character bbox and intersects them with the character mask. This is limb separation by geometry, not semantic body-part segmentation. |
| Inpainting / background reconstruction | **PARTIAL** | `inpainting/lama_inpainter.py` attempts a LaMa adapter only if configured, but `saicinpainting` is not installed. The actual working reconstruction is OpenCV `cv2.inpaint` using Telea and Navier-Stokes. This is real classical inpainting, not LaMa or Stable Diffusion. |
| Export system | **WORKING** | `exporters/layer_exporter.py` writes panel images, background images, speech/text/effects folders, character alpha PNGs, body-part PNGs, and debug overlays. `exporters/rig_exporter.py` writes rig JSON with hierarchy, bboxes, pivots, and confidence. |
| GUI | **PARTIAL** | GUI exists in `gui.py` and uses PySide6. It includes dockable panels, dark theme, image viewer, project explorer, properties panel, processing console, progress bar, and settings dialog. It remains partial because it is still a wrapper around the heuristic pipeline rather than a full production editing application. |
| CUDA / GPU acceleration | **PARTIAL / NOT USED HERE** | `utils/gpu.py` detects CUDA with `torch.cuda.is_available()` and sets runtime metadata. In this environment, `torch.cuda.is_available()` is false, so runtime device is CPU. No real inference model is loaded on CUDA. ONNX Runtime CUDA provider is present, but no ONNX model inference is used. |
| Model caching | **WORKING FOR HOOKS** | `utils/model_cache.py` caches loaded optional backends. In practice, only the failed/None MediaPipe loader is cached in this environment; heavy models are not installed. |
| Benchmarking | **WORKING** | `utils/performance.py` records stage timings, CPU samples, VRAM samples, model load timings, and writes JSON/Markdown reports. VRAM remains 0 MB here because CUDA is not available/used. |

## Specific answers

### 1. Is SAM2 actually installed and used?

**No.**

Evidence:

- Installed package check reports `sam2: missing`.
- `requirements.txt` does not list `sam2`.
- `segmentation/sam_segmenter.py` only imports `sam2` when `config.models.sam2_checkpoint` is configured.
- The actual default segmentation path is `_fallback_segment`, which uses OpenCV thresholding/morphology.

Classification: **PLACEHOLDER AI integration, PARTIAL functional fallback**.

### 2. Is GroundingDINO actually installed and used?

**No.**

Evidence:

- Installed package check reports `groundingdino: missing`.
- `requirements.txt` does not list GroundingDINO.
- `detectors/character_detector.py` only imports `groundingdino.util.inference` when checkpoint paths are configured.
- The current working path is `_fallback_detect`, which uses OpenCV contours and a central ellipse fallback.

Classification: **PLACEHOLDER AI integration, PARTIAL functional fallback**.

### 3. Is MediaPipe actually installed and used?

**No.**

Evidence:

- Installed package check reports `mediapipe: missing`.
- Runtime logs during processing report `MediaPipe unavailable: No module named 'mediapipe'`.
- `requirements.txt` does not list MediaPipe.
- `detectors/pose_detector.py` falls back to `_estimate_geometric`.

Classification: **PLACEHOLDER optional dependency, PARTIAL geometric fallback**.

### 4. Is LaMa actually installed and used?

**No.**

Evidence:

- Installed package check reports `saicinpainting: missing`.
- `requirements.txt` does not list LaMa/saicinpainting.
- `inpainting/lama_inpainter.py` imports `saicinpainting` only when `lama_checkpoint` is configured.
- The default working path is OpenCV `cv2.inpaint`.

Classification: **PLACEHOLDER AI integration, PARTIAL OpenCV fallback**.

### 5. Is CUDA actually used?

**No, not in this environment and not by the current fallback pipeline.**

Evidence:

- `torch.cuda.is_available(): False`.
- `system-info` reports `Device: cpu`, `GPU: not detected`, and mixed precision false.
- No real Torch/ONNX model inference is executed in the default pipeline.
- ONNX Runtime CUDA provider is installed, but no ONNX model is loaded or run.

Classification: **PARTIAL detection only, not actively used**.

### 6. Is the RTX 5060 utilized?

**No.**

Evidence:

- This environment does not expose an RTX 5060 or any CUDA GPU.
- `torch.cuda.is_available()` is false and GPU name is not detected.
- The code would select CUDA if available, but there is no evidence of RTX 5060 utilization in this audit.

Classification: **NOT USED**.

### 7. Is the GUI PySide6 or Tkinter?

**PySide6 after the GUI migration.**

Evidence:

- `MangaAnimatorPrep/gui.py` imports `from PySide6 import QtCore, QtGui, QtWidgets`.
- `requirements.txt` lists `PySide6`.
- The CLI smoke test exercises `python3 -m MangaAnimatorPrep.main gui --smoke-test`.

Classification: **PySide6 GUI, PARTIAL production UX**.

### 8. Are body parts actually separated into limbs?

**Yes, but only by geometric mask slicing, not by semantic AI parsing.**

Evidence:

- `BodyPartSplitter.PART_PARENTS` defines head, hair, torso, upper/lower arms, hands, upper/lower legs, and feet.
- `_geometric_regions` creates fixed rectangles for each body part over the character bounding box.
- The output part masks are `cv2.bitwise_and(character_mask, region_mask)`.

Classification: **PARTIAL**.

### 9. Is there real AI segmentation or mocked segmentation?

**There is no real AI segmentation currently used. It is an OpenCV fallback, not a mock object.**

Evidence:

- SAM2 is missing.
- `_fallback_segment` in `sam_segmenter.py` uses thresholding and morphology.
- It creates real masks from image pixels, but not from a trained segmentation model.

Classification: **PARTIAL fallback, AI segmentation placeholder**.

### 10. Is there real background reconstruction or placeholder reconstruction?

**There is real classical OpenCV inpainting, but not real LaMa/Stable Diffusion reconstruction.**

Evidence:

- `LaMaInpainter._opencv_inpaint` uses `cv2.inpaint` with `cv2.INPAINT_TELEA` and `cv2.INPAINT_NS`.
- LaMa is not installed.
- Stable Diffusion is not wired despite a config field.

Classification: **PARTIAL**.

## Honest completion estimate

These percentages judge production-quality completion against the requested feature set, not whether the demo pipeline can run.

- **Architecture Complete:** 60%
  - The module layout, config, CLI, GUI wrapper, exporters, reports, and fallback pipeline exist.
  - Major AI integrations are adapter hooks rather than validated production integrations.

- **Functional Complete:** 35%
  - The application can process images, detect simple panels, produce approximate masks/layers, export folders, and generate reports.
  - Most advanced requirements are heuristic approximations: character detection, segmentation, pose, limb parsing, text/effects detection, and background reconstruction.

- **Production Ready:** 15%
  - Not production-ready for the original AI requirements.
  - Missing installed/validated SAM2, GroundingDINO, MediaPipe, LaMa, Stable Diffusion/OpenPose, real CUDA inference, model downloads, accuracy benchmarks on real manga, and robust GUI UX.

