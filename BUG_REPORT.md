# Bug Report

## Prioritized task list

1. **P0 - GUI missing / GUI launch path unavailable**
   - Cause: the project only exposed CLI commands, despite being intended as a local desktop app.
   - Fix: added `MangaAnimatorPrep/gui.py`; later migrated it from Tkinter to required PySide6.
   - Test: `python3 -m MangaAnimatorPrep.main gui --smoke-test --smoke-input sample_data/sample_page.png --smoke-output gui_smoke_output` validates launch, image loading, and processing.

2. **P0 - Optional model adapter placeholders could crash runtime**
   - Cause: `GroundingDinoAdapter`, `SAM2Adapter`, and `LaMaAdapter` contained `NotImplementedError` paths. In the GroundingDINO case, configuring checkpoint paths could raise before fallback detection ran.
   - Fix: replaced placeholder crashes with safe dynamic adapters that try common package APIs and fall back to the existing OpenCV implementation when model construction or inference fails.
   - Test: added regression tests for configured-but-unavailable GroundingDINO, SAM2, and LaMa paths. `python3 -m pytest -q` passes.

3. **P0 - Nested JSON config loading was unsafe**
   - Cause: `AppConfig.from_file()` used shallow `model_copy(update=data)`, which can replace nested Pydantic config models with plain dictionaries.
   - Fix: added validated deep merge before `AppConfig.model_validate()`.
   - Test: added `test_nested_config_file_is_validated`; `python3 -m pytest -q` passes.

4. **P1 - Tkinter dependency missing in cloud runtime**
   - Status: superseded.
   - Fix: Tkinter was removed from the GUI stack and replaced with PySide6.
   - Test: PySide6 GUI smoke tests now cover launch, image loading, and processing.

5. **P1 - GUI worker thread updated Tk state directly**
   - Cause: pipeline processing runs in a background thread, but completion/failure status updates were written directly to Tk variables.
   - Fix: routed status updates through `root.after(...)`.
   - Test: GUI smoke test and pytest suite pass.

6. **P1 - CUDA unavailable in the cloud machine**
   - Cause: this runtime has no visible NVIDIA device; `torch.cuda.is_available()` returns `False`.
   - Fix: no code fix required; CPU fallback is working. CUDA selection remains automatic for the target RTX 5060 when PyTorch sees the GPU.
   - Test: `python3 -m MangaAnimatorPrep.main system-info` reports CPU fallback, PyTorch available, and ONNX Runtime CUDA/CPU providers.

7. **P2 - Model downloads are not fully automated**
   - Cause: GroundingDINO, SAM2, LaMa, and OpenPose checkpoints have large files, varying licenses, and changing upstream URLs.
   - Fix: model cache directories and checksum reporting are implemented; production checkpoint retrieval remains documented/manual.
   - Test: `python3 scripts/download_models.py --models-dir MangaAnimatorPrep/models --verify` succeeds and reports expected files.

## Runtime verification commands

```bash
python3 -m compileall MangaAnimatorPrep scripts tests
python3 -m pip check
python3 -m MangaAnimatorPrep.main system-info
python3 -m MangaAnimatorPrep.main gui --smoke-test
python3 -m pytest -q
python3 scripts/create_sample_data.py
python3 -m MangaAnimatorPrep.main process sample_data --output output --debug
python3 -m MangaAnimatorPrep.main benchmark sample_data --output output_benchmark --debug
```

