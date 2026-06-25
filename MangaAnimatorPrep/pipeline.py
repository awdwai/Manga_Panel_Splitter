"""End-to-end manga animation preparation pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from MangaAnimatorPrep.config import AppConfig
from MangaAnimatorPrep.detectors.character_detector import CharacterDetector
from MangaAnimatorPrep.detectors.effect_detector import EffectDetector
from MangaAnimatorPrep.detectors.panel_detector import PanelDetector
from MangaAnimatorPrep.detectors.pose_detector import PoseDetector
from MangaAnimatorPrep.detectors.speech_detector import SpeechDetector
from MangaAnimatorPrep.detectors.text_detector import TextDetector
from MangaAnimatorPrep.exporters.layer_exporter import LayerExporter
from MangaAnimatorPrep.exporters.rig_exporter import RigExporter
from MangaAnimatorPrep.inpainting.lama_inpainter import LaMaInpainter
from MangaAnimatorPrep.segmentation.body_part_splitter import BodyPartSplitter
from MangaAnimatorPrep.segmentation.sam_segmenter import SAMSegmenter
from MangaAnimatorPrep.types import Detection, PanelResult
from MangaAnimatorPrep.utils.file_utils import ensure_dir, list_images, numbered_name
from MangaAnimatorPrep.utils.gpu import RuntimeInfo, empty_cuda_cache, resolve_runtime
from MangaAnimatorPrep.utils.image_utils import crop_with_bbox, draw_detections, load_image, normalize_mask, save_rgb
from MangaAnimatorPrep.utils.model_cache import GLOBAL_MODEL_CACHE
from MangaAnimatorPrep.utils.performance import (
    PanelMetrics,
    PerformanceTracker,
    write_benchmark_markdown,
    write_performance_report,
)

LOGGER = logging.getLogger(__name__)


class MangaAnimatorPipeline:
    """Coordinate detection, segmentation, reconstruction, rigging, and export."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.runtime: RuntimeInfo = resolve_runtime(config.device)
        self.tracker = PerformanceTracker(self.runtime)
        self.panel_detector = PanelDetector(config)
        self.character_detector = CharacterDetector(config)
        self.speech_detector = SpeechDetector(config)
        self.text_detector = TextDetector(config)
        self.effect_detector = EffectDetector(config)
        self.segmenter = SAMSegmenter(config)
        self.pose_detector = PoseDetector(config)
        self.body_part_splitter = BodyPartSplitter()
        self.inpainter = LaMaInpainter(config)
        self.layer_exporter = LayerExporter()
        self.rig_exporter = RigExporter()

    def process_path(self, input_path: Path, output_dir: Path, debug: bool | None = None) -> list[PanelResult]:
        ensure_dir(output_dir)
        images = list_images(input_path)
        if not images:
            raise ValueError(f"No supported images found in {input_path}")
        all_results: list[PanelResult] = []
        all_metrics: list[PanelMetrics] = []

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), TimeElapsedColumn()) as progress:
            task = progress.add_task("Processing manga images", total=len(images))
            panel_offset = 0
            for image_path in images:
                results, metrics = self.process_image(image_path, output_dir, panel_offset, bool(self.config.output.debug if debug is None else debug))
                panel_offset += len(results)
                all_results.extend(results)
                all_metrics.extend(metrics)
                progress.advance(task)

        if self.config.output.save_performance_json:
            write_performance_report(output_dir / "performance_report.json", all_metrics, self.runtime)
        if self.config.output.save_benchmark_markdown:
            write_benchmark_markdown(output_dir / "BENCHMARK_RESULTS.md", all_metrics, self.runtime)
        return all_results

    def process_image(
        self,
        image_path: Path,
        output_dir: Path,
        panel_offset: int = 0,
        debug: bool = False,
    ) -> tuple[list[PanelResult], list[PanelMetrics]]:
        LOGGER.info("Processing image: %s", image_path)
        image = load_image(image_path)
        metrics: list[PanelMetrics] = []
        with self.tracker.measure("panel_detection", image=str(image_path)):
            panel_detections = self.panel_detector.detect(image)
        if debug:
            debug_dir = ensure_dir(output_dir / "debug")
            save_rgb(debug_dir / f"{image_path.stem}_panel_outlines.png", draw_detections(image, panel_detections))

        results: list[PanelResult] = []
        for local_index, panel_detection in enumerate(panel_detections, start=1):
            panel_index = panel_offset + local_index
            panel_id = f"panel_{panel_index:03d}"
            start_record = len(self.tracker.records)
            panel = crop_with_bbox(image, panel_detection.bbox)
            panel_dir = ensure_dir(output_dir / panel_id)
            panel_path = self.layer_exporter.export_panel_image(panel_dir, panel_index, panel)

            with self.tracker.measure("character_detection", panel=panel_id):
                characters = self.character_detector.detect(panel)
            with self.tracker.measure("speech_detection", panel=panel_id):
                speech = self.speech_detector.detect(panel)
            with self.tracker.measure("text_detection", panel=panel_id):
                text = self.text_detector.detect(panel)
            with self.tracker.measure("effect_detection", panel=panel_id):
                effects = self.effect_detector.detect(panel)

            self.layer_exporter.export_detection_layers(panel_dir, "speech", panel, speech)
            self.layer_exporter.export_detection_layers(panel_dir, "text", panel, text)
            self.layer_exporter.export_detection_layers(panel_dir, "effects", panel, effects)

            character_masks: list[np.ndarray] = []
            all_detections: list[Detection] = [*characters, *speech, *text, *effects]
            for character_index, character in enumerate(characters, start=1):
                with self.tracker.measure("character_segmentation", panel=panel_id, character=character_index):
                    char_mask = self.segmenter.segment(panel, character)
                character_masks.append(normalize_mask(char_mask))

            overlap_info = self._compute_instance_overlaps(character_masks)
            for overlap in overlap_info["pairs"]:
                LOGGER.warning(
                    "Ambiguous character overlap in %s: %s <-> %s confidence=%.3f pixels=%s",
                    panel_id,
                    overlap["character_a"],
                    overlap["character_b"],
                    overlap["overlap_confidence"],
                    overlap["intersection_pixels"],
                )

            for character_index, (character, char_mask) in enumerate(zip(characters, character_masks, strict=False), start=1):
                character_id = f"character_{character_index:03d}"
                with self.tracker.measure("pose_estimation", panel=panel_id, character=character_index):
                    keypoints = self.pose_detector.estimate(panel, char_mask, character.bbox)
                with self.tracker.measure("body_part_segmentation", panel=panel_id, character=character_index):
                    body_parts, body_metadata = self.body_part_splitter.analyze(
                        char_mask,
                        keypoints,
                        panel=panel,
                        ambiguous_mask=overlap_info["ambiguous_masks"][character_index - 1],
                    )
                character_metadata = self._build_character_metadata(
                    character_id,
                    character,
                    char_mask,
                    body_metadata,
                    overlap_info,
                    character_index - 1,
                )
                char_dir = self.layer_exporter.export_character(
                    panel_dir,
                    character_index,
                    panel,
                    char_mask,
                    body_parts,
                    metadata=character_metadata,
                )
                self.rig_exporter.export(char_dir / "rig.json", body_parts, keypoints)
                if character_index == 1:
                    self.rig_exporter.export(panel_dir / "rig.json", body_parts, keypoints)
                if debug:
                    self.layer_exporter.export_debug(
                        panel_dir,
                        panel,
                        characters=characters,
                        character_mask=char_mask,
                        keypoints=keypoints,
                        body_parts=body_parts,
                    )

            removal_mask = self._union_masks(character_masks, panel.shape[:2])
            with self.tracker.measure("background_reconstruction", panel=panel_id):
                background = self.inpainter.inpaint(panel, removal_mask)
            self.layer_exporter.export_background(panel_dir, background)
            if debug and not character_masks:
                self.layer_exporter.export_debug(panel_dir, panel, characters=characters)

            panel_metrics = self.tracker.build_panel_metrics(panel_id, GLOBAL_MODEL_CACHE.load_times(), start_record)
            metrics.append(panel_metrics)
            results.append(
                PanelResult(
                    panel_index=panel_index,
                    panel_path=panel_path,
                    output_dir=panel_dir,
                    detections=all_detections,
                    metrics={"total_seconds": panel_metrics.total_seconds},
                )
            )
            empty_cuda_cache()
        return results, metrics

    def _union_masks(self, masks: list[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
        union = np.zeros(shape, dtype=np.uint8)
        for mask in masks:
            union = cv2.bitwise_or(union, normalize_mask(mask))
        return union

    def _compute_instance_overlaps(self, masks: list[np.ndarray]) -> dict[str, object]:
        if not masks:
            return {"pairs": [], "ambiguous_masks": [], "ambiguous_union": None}
        binary_masks = [np.where(normalize_mask(mask) > 0, 255, 0).astype(np.uint8) for mask in masks]
        ambiguous_masks = [np.zeros_like(binary_masks[0]) for _ in binary_masks]
        ambiguous_union = np.zeros_like(binary_masks[0])
        pairs: list[dict[str, object]] = []
        areas = [max(1, int(cv2.countNonZero(mask))) for mask in binary_masks]
        for i in range(len(binary_masks)):
            for j in range(i + 1, len(binary_masks)):
                intersection = cv2.bitwise_and(binary_masks[i], binary_masks[j])
                intersection_pixels = int(cv2.countNonZero(intersection))
                if intersection_pixels == 0:
                    continue
                confidence = float(intersection_pixels / max(1, min(areas[i], areas[j])))
                ambiguous_masks[i] = cv2.bitwise_or(ambiguous_masks[i], intersection)
                ambiguous_masks[j] = cv2.bitwise_or(ambiguous_masks[j], intersection)
                ambiguous_union = cv2.bitwise_or(ambiguous_union, intersection)
                pairs.append(
                    {
                        "character_a": f"character_{i + 1:03d}",
                        "character_b": f"character_{j + 1:03d}",
                        "intersection_pixels": intersection_pixels,
                        "overlap_confidence": confidence,
                    }
                )
        return {"pairs": pairs, "ambiguous_masks": ambiguous_masks, "ambiguous_union": ambiguous_union}

    def _build_character_metadata(
        self,
        character_id: str,
        detection: Detection,
        mask: np.ndarray,
        body_metadata: dict[str, object],
        overlap_info: dict[str, object],
        character_offset: int,
    ) -> dict[str, object]:
        mask_binary = np.where(normalize_mask(mask) > 0, 255, 0).astype(np.uint8)
        ambiguous_masks = overlap_info["ambiguous_masks"]
        ambiguous_mask = ambiguous_masks[character_offset] if isinstance(ambiguous_masks, list) else np.zeros_like(mask_binary)
        ambiguous_pixels = int(cv2.countNonZero(ambiguous_mask))
        total_pixels = max(1, int(cv2.countNonZero(mask_binary)))
        overlap_pairs = [
            pair
            for pair in overlap_info["pairs"]
            if isinstance(pair, dict) and character_id in {pair.get("character_a"), pair.get("character_b")}
        ]
        warnings = list(body_metadata.get("warnings", [])) if isinstance(body_metadata.get("warnings"), list) else []
        if ambiguous_pixels:
            warnings.append("Character overlaps another instance; ambiguous pixels are preserved and reported.")
        return {
            "schema_version": "1.0",
            "character_id": character_id,
            "detection": {
                "bbox": detection.bbox.to_dict(),
                "confidence": detection.confidence,
                "label": detection.label,
            },
            "mask": {
                "total_pixels": total_pixels,
                "owned_pixels": max(0, total_pixels - ambiguous_pixels),
                "ambiguous_pixels": ambiguous_pixels,
                "ambiguity_ratio": float(ambiguous_pixels / total_pixels),
            },
            "overlaps": overlap_pairs,
            "body": body_metadata,
            "warnings": warnings,
        }

