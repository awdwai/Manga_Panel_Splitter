# Installation Report

Status: verified in the cloud environment.

The application is designed for Python 3.14+ on Windows 11 with an NVIDIA RTX 5060, CUDA, and GPU-first inference. The cloud verification environment uses Python 3.12, so dependency verification here validates code paths and CPU fallbacks while preserving CUDA-first runtime detection for the target machine.

## Dependency strategy

- Core runtime dependencies are listed in `requirements.txt`.
- PyTorch and ONNX Runtime GPU are installed from package-manager defaults unless a CUDA-specific wheel/index is required by the target machine.
- Heavy model repositories/checkpoints are lazy optional backends; the app runs with deterministic CPU fallbacks when they are absent.

## Commands

```bash
python3 -m pip install -r requirements.txt
python3 scripts/download_models.py --models-dir MangaAnimatorPrep/models --verify
python3 -m MangaAnimatorPrep.main system-info
python3 -m pytest -q
```

## Verification results

- Dependency installation: success.
  - Installed latest package-manager versions into the user site because system site-packages are not writable.
  - Installed PyTorch, TorchVision, ONNX Runtime GPU, OpenCV headless, Pillow, Pydantic, Rich, tqdm, psutil, and pytest.
- Model cache setup: success.
  - Created `MangaAnimatorPrep/models/{groundingdino,sam2,lama,openpose}`.
  - Checkpoints are not bundled; the script reports expected files and supports SHA256 verification for files placed in the cache.
- Runtime probe:
  - PyTorch available: yes.
  - `torch.cuda.is_available()`: false in this cloud machine.
  - Device selected here: CPU fallback.
  - ONNX Runtime providers: `CUDAExecutionProvider`, `CPUExecutionProvider`.
  - RTX 5060 target behavior: CUDA will be selected automatically when the NVIDIA driver/device is visible to PyTorch.
- Tests:
  - `python3 -m pytest -q`
  - Result: `5 passed`.
- Sample execution:
  - `python3 scripts/create_sample_data.py`
  - `python3 -m MangaAnimatorPrep.main process sample_data --output output --debug`
  - Result: processed 3 panels and generated panel folders, backgrounds, transparent character/body-part layers, rig JSON, and debug overlays.
- Benchmark execution:
  - `python3 -m MangaAnimatorPrep.main benchmark sample_data --output output_benchmark --debug`
  - Result: processed 3 panels and generated `output_benchmark/BENCHMARK_RESULTS.md` plus `output_benchmark/performance_report.json`.

