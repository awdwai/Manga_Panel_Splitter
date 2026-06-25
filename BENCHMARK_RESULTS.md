# Benchmark Results

Status: verified on synthetic sample data.

Command:

```bash
python3 -m MangaAnimatorPrep.main benchmark sample_data --output output --debug
```

Cloud environment results:

- Device: `cpu`
- CUDA available: `False`
- Mixed precision: `False`
- GPU: `not detected`
- ONNX providers: `CUDAExecutionProvider, CPUExecutionProvider`
- Panels processed: `3`
- Total processing time: `0.6466s`
- Average time per panel: `0.2155s`
- Peak VRAM usage: `0.00 MB`
- Peak CPU usage sample: `392.80%`

| Panel | Total (s) | Peak VRAM (MB) | Peak CPU (%) | Main stages |
|---|---:|---:|---:|---|
| panel_001 | 0.1416 | 0.00 | 392.80 | character_detection=0.030s, speech_detection=0.035s, text_detection=0.030s, effect_detection=0.032s, character_segmentation=0.000s, pose_estimation=0.001s, body_part_segmentation=0.005s, background_reconstruction=0.009s |
| panel_002 | 0.1476 | 0.00 | 171.60 | character_detection=0.032s, speech_detection=0.033s, text_detection=0.032s, effect_detection=0.034s, character_segmentation=0.000s, pose_estimation=0.000s, body_part_segmentation=0.006s, background_reconstruction=0.010s |
| panel_003 | 0.3574 | 0.00 | 252.80 | character_detection=0.078s, speech_detection=0.079s, text_detection=0.078s, effect_detection=0.081s, character_segmentation=0.001s, pose_estimation=0.000s, body_part_segmentation=0.016s, background_reconstruction=0.024s |

The target Windows 11 RTX 5060 environment should report `cuda` as the selected device and non-zero VRAM usage when the NVIDIA driver and CUDA-enabled PyTorch are visible.

