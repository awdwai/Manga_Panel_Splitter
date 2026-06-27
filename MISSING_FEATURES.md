# Missing / Partial Features

These items are not blockers for the currently working fallback pipeline, but they remain partial for production-grade AI quality.

## Production model integration

| Feature | Status | Reason |
|---|---|---|
| GroundingDINO character detection | Partial | Adapter attempts common `groundingdino.util.inference` APIs, but real checkpoint/config files are not bundled. |
| SAM2 segmentation | Partial | Adapter attempts common SAM2 APIs, but real SAM2 package/checkpoint/config validation must happen in the target environment. |
| LaMa inpainting | Partial | OpenCV fallback works; LaMa packages expose different APIs and checkpoint formats. |
| Stable Diffusion inpainting fallback | Partial | Config field exists, but no diffusers pipeline is wired yet. |
| OpenPose fallback | Partial | MediaPipe/geometric fallback works; OpenPose model loading is not implemented. |
| Full automated checkpoint download | Partial | Large/licensed model artifacts are not downloaded automatically. Cache setup and checksum reporting are implemented. |
| Semantic body-part segmentation | Partial | Automatic geometric slicing has been disabled; approved semantic/correction masks are required before body-part PNG export. |
| Production boundary editor handles | Partial | GUI supports selected-part boxes, numeric boundary editing, edge snapping, and per-part resegmentation; full transform handles can be refined further. |

## Accuracy limitations

- Borderless/irregular panel detection uses heuristics and may need additional training/model logic for difficult production pages.
- Character detection fallback is silhouette/ink-blob based and can confuse dense backgrounds with characters.
- Body-part export is approval-gated and table-driven; without approved semantic masks it records missing/unknown parts instead of inventing anatomy.
- Speech/text/effects detection use OpenCV heuristics and may need OCR or specialized detectors for complex pages.

## Environment limitations found during QA

- This cloud environment has no visible NVIDIA GPU; CUDA code paths are present but could not be exercised here.
- GUI stack has been migrated to PySide6; headless CI/cloud verification should set `QT_QPA_PLATFORM=offscreen`.
- MediaPipe is not in `requirements.txt`; pose falls back to geometry unless users install MediaPipe separately.

## Next highest-value improvements

1. Add approved checkpoint download URLs/checksums once model licensing/source choices are finalized.
2. Add integration tests on a Windows 11 RTX 5060 machine to exercise CUDA/FP16/VRAM paths.
3. Add real sample manga pages with expected panel/character masks for accuracy regression tests.
4. Wire a human parsing/body-part segmentation model for better body-part layers.
5. Add OCR-backed text extraction/removal if text content needs to be preserved separately.

