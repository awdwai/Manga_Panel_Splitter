# Installation Report

Status: pending verification.

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

Verification results will be updated after execution.

