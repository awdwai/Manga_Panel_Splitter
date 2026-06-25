"""PySide6 desktop GUI for MangaAnimatorPrep."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from MangaAnimatorPrep.config import load_config
from MangaAnimatorPrep.interactive_segmentation import InteractiveSegmentationSession
from MangaAnimatorPrep.pipeline import MangaAnimatorPipeline
from MangaAnimatorPrep.types import BoundingBox, Detection
from MangaAnimatorPrep.workflow import DetectionSession, DetectionWorkflow, PanelDraft
from MangaAnimatorPrep.utils.file_utils import list_images
from MangaAnimatorPrep.utils.gpu import resolve_runtime, torch_cuda_available
from MangaAnimatorPrep.utils.image_utils import load_image, normalize_mask


def _import_qt() -> dict[str, Any]:
    """Import PySide6 modules in one place so failures are explicit."""

    from PySide6 import QtCore, QtGui, QtWidgets

    return {"QtCore": QtCore, "QtGui": QtGui, "QtWidgets": QtWidgets}


def _ensure_app() -> Any:
    qt = _import_qt()
    QtWidgets = qt["QtWidgets"]
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    app.setApplicationName("MangaAnimatorPrep")
    return app


class PipelineWorker:
    """QObject worker that runs the existing pipeline on a QThread."""

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        config_path: Path | None,
        debug: bool,
        benchmark: bool,
        workflow_options: dict[str, object],
    ) -> None:
        qt = _import_qt()
        QtCore = qt["QtCore"]

        class _Worker(QtCore.QObject):
            log = QtCore.Signal(str)
            progress = QtCore.Signal(int)
            finished = QtCore.Signal(int)
            failed = QtCore.Signal(str)

            def run(self_inner: Any) -> None:
                try:
                    config = load_config(config_path)
                    config.output.debug = debug
                    apply_workflow_options(config, workflow_options)
                    if benchmark:
                        config.output.save_benchmark_markdown = True
                        config.output.save_performance_json = True
                    self_inner.log.emit(f"Input: {input_path}")
                    self_inner.log.emit(f"Output: {output_path}")
                    self_inner.progress.emit(10)
                    results = MangaAnimatorPipeline(config).process_path(input_path, output_path, debug=debug)
                    self_inner.progress.emit(100)
                    self_inner.finished.emit(len(results))
                except Exception as exc:  # pragma: no cover - GUI thread integration
                    self_inner.failed.emit(str(exc))

        self.obj = _Worker()


class SettingsDialog:
    """Settings dialog for runtime and output preferences."""

    def __init__(self, parent: Any) -> None:
        qt = _import_qt()
        QtWidgets = qt["QtWidgets"]
        self.dialog = QtWidgets.QDialog(parent.window)
        self.dialog.setWindowTitle("Settings")
        layout = QtWidgets.QFormLayout(self.dialog)
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])
        self.batch_size = QtWidgets.QSpinBox()
        self.batch_size.setRange(1, 64)
        self.batch_size.setValue(parent.batch_size)
        self.debug_checkbox = QtWidgets.QCheckBox("Write debug visualizations")
        self.debug_checkbox.setChecked(parent.debug_enabled)
        layout.addRow("Device preference", self.device_combo)
        layout.addRow("Batch size", self.batch_size)
        layout.addRow("", self.debug_checkbox)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.dialog.accept)
        buttons.rejected.connect(self.dialog.reject)
        layout.addRow(buttons)

    def exec(self) -> int:
        return int(self.dialog.exec())


class MangaAnimatorPrepMainWindow:
    """PySide6 main window with dockable panels and the existing processing pipeline."""

    def __init__(self, config_path: Path | None = None) -> None:
        qt = _import_qt()
        QtCore = qt["QtCore"]
        QtGui = qt["QtGui"]
        QtWidgets = qt["QtWidgets"]
        self.QtCore = QtCore
        self.QtGui = QtGui
        self.QtWidgets = QtWidgets
        self.config_path = config_path
        self.debug_enabled = True
        self.batch_size = 4
        self.input_path: Path | None = None
        self.output_path = Path("output")
        self.worker_thread: Any | None = None
        self.worker: Any | None = None
        self.detection_session: DetectionSession | None = None
        self.detections_approved = False
        self.overlay_items: list[Any] = []
        self.segmentation_overlay_items: list[Any] = []
        self.panel_expected_character_controls: dict[str, Any] = {}
        self.brush_correction_enabled = False
        self.segmentation_session: InteractiveSegmentationSession | None = None
        self.interactive_segmentation_enabled = False
        self._brush_erase = False

        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle("MangaAnimatorPrep")
        self.window.resize(1280, 820)
        self.window.setDockOptions(
            QtWidgets.QMainWindow.AllowNestedDocks
            | QtWidgets.QMainWindow.AllowTabbedDocks
            | QtWidgets.QMainWindow.AnimatedDocks
        )
        self._apply_dark_theme()
        self._build_central_image_viewer()
        self._build_actions()
        self._build_docks()
        self._build_status_bar()
        self._log("PySide6 GUI ready.")
        self._original_viewport_mouse_press = self.image_view.viewport().mousePressEvent
        self.image_view.viewport().mousePressEvent = self._image_mouse_press_event  # type: ignore[method-assign]

    def show(self) -> None:
        self.window.show()

    def close(self) -> None:
        self.window.close()

    def load_image_path(self, path: Path) -> bool:
        if not path.exists():
            self._log(f"Image load failed: {path} does not exist")
            return False
        images = list_images(path)
        if not images:
            self._log(f"Image load failed: no supported images found in {path}")
            return False
        self.input_path = path
        first_image = images[0]
        self.current_image_array = load_image(first_image)
        self.segmentation_session = InteractiveSegmentationSession(self.current_image_array)
        self.detections_approved = False
        pixmap = self.QtGui.QPixmap(str(first_image))
        if pixmap.isNull():
            array = self.current_image_array
            height, width = array.shape[:2]
            image = self.QtGui.QImage(array.data, width, height, 3 * width, self.QtGui.QImage.Format_RGB888).copy()
            pixmap = self.QtGui.QPixmap.fromImage(image)
        self.image_scene.clear()
        self.image_scene.addPixmap(pixmap)
        self.image_scene.setSceneRect(pixmap.rect())
        self.image_view.fitInView(self.image_scene.sceneRect(), self.QtCore.Qt.KeepAspectRatio)
        self._populate_project_tree(path, images)
        self._set_property("Input", str(path))
        self._set_property("First image", str(first_image))
        self._set_property("Image count", str(len(images)))
        self._log(f"Loaded {first_image}")
        self._refresh_layer_tree()
        return True

    def run_processing_blocking(self, input_path: Path, output_path: Path, benchmark: bool = False) -> int:
        config = load_config(self.config_path)
        config.output.debug = self.debug_enabled
        config.device.batch_size = self.batch_size
        apply_workflow_options(config, self._workflow_options())
        if benchmark:
            config.output.save_benchmark_markdown = True
            config.output.save_performance_json = True
        self.progress_bar.setValue(10)
        self._log("Processing started.")
        results = MangaAnimatorPipeline(config).process_path(input_path, output_path, debug=self.debug_enabled)
        self.progress_bar.setValue(100)
        self.output_path = output_path
        self._set_property("Output", str(output_path))
        self._set_property("Panels processed", str(len(results)))
        self._log(f"Processing complete: {len(results)} panel(s).")
        return len(results)

    def _apply_dark_theme(self) -> None:
        self.window.setStyleSheet(
            """
            QMainWindow, QWidget { background: #1f232a; color: #e6e6e6; }
            QMenuBar, QMenu, QToolBar, QStatusBar { background: #171a20; color: #e6e6e6; }
            QDockWidget::title { background: #2b3039; padding: 6px; }
            QPushButton, QToolButton { background: #323844; border: 1px solid #4b5565; padding: 6px; }
            QPushButton:hover, QToolButton:hover { background: #3d4656; }
            QLineEdit, QTextEdit, QPlainTextEdit, QTreeWidget, QTableWidget, QGraphicsView {
                background: #111318; color: #f0f0f0; border: 1px solid #3a404c;
            }
            QHeaderView::section { background: #2b3039; color: #e6e6e6; padding: 4px; }
            QProgressBar { border: 1px solid #4b5565; text-align: center; background: #111318; }
            QProgressBar::chunk { background: #4e9af1; }
            """
        )

    def _build_central_image_viewer(self) -> None:
        self.image_scene = self.QtWidgets.QGraphicsScene()
        self.image_view = self.QtWidgets.QGraphicsView(self.image_scene)
        self.image_view.setDragMode(self.QtWidgets.QGraphicsView.ScrollHandDrag)
        self.image_view.setRenderHint(self.QtGui.QPainter.Antialiasing)
        self.window.setCentralWidget(self.image_view)

    def _build_actions(self) -> None:
        file_menu = self.window.menuBar().addMenu("&File")
        tools_menu = self.window.menuBar().addMenu("&Tools")
        toolbar = self.window.addToolBar("Main")

        open_image = self.QtGui.QAction("Open Image", self.window)
        open_image.triggered.connect(self._choose_image)
        open_folder = self.QtGui.QAction("Open Folder", self.window)
        open_folder.triggered.connect(self._choose_folder)
        choose_output = self.QtGui.QAction("Choose Output", self.window)
        choose_output.triggered.connect(self._choose_output)
        process = self.QtGui.QAction("Process", self.window)
        process.triggered.connect(lambda: self._start_processing(False))
        benchmark = self.QtGui.QAction("Benchmark", self.window)
        benchmark.triggered.connect(lambda: self._start_processing(True))
        settings = self.QtGui.QAction("Settings", self.window)
        settings.triggered.connect(self._open_settings)
        system_info = self.QtGui.QAction("System Info", self.window)
        system_info.triggered.connect(self._show_system_info)

        for action in [open_image, open_folder, choose_output, process, benchmark]:
            file_menu.addAction(action)
            toolbar.addAction(action)
        tools_menu.addAction(settings)
        tools_menu.addAction(system_info)
        toolbar.addSeparator()
        toolbar.addAction(settings)
        toolbar.addAction(system_info)

    def _build_docks(self) -> None:
        self._build_detection_controls()
        self._build_interactive_segmentation_controls()

        self.project_tree = self.QtWidgets.QTreeWidget()
        self.project_tree.setHeaderLabels(["Project Explorer"])
        self._add_dock("Project Explorer", self.project_tree, self.QtCore.Qt.LeftDockWidgetArea)

        self.properties_table = self.QtWidgets.QTableWidget(0, 2)
        self.properties_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.properties_table.horizontalHeader().setStretchLastSection(True)
        self._add_dock("Properties", self.properties_table, self.QtCore.Qt.RightDockWidgetArea)

        self.console = self.QtWidgets.QPlainTextEdit()
        self.console.setReadOnly(True)
        self._add_dock("Processing Console", self.console, self.QtCore.Qt.BottomDockWidgetArea)

    def _build_interactive_segmentation_controls(self) -> None:
        panel = self.QtWidgets.QWidget()
        layout = self.QtWidgets.QVBoxLayout(panel)

        self.interactive_segmentation_checkbox = self.QtWidgets.QCheckBox("Enable Click-to-Segment")
        self.interactive_segmentation_checkbox.toggled.connect(self._toggle_interactive_segmentation)
        self.layer_label_edit = self.QtWidgets.QLineEdit()
        self.layer_label_edit.setPlaceholderText("Layer label")
        self.layer_label_edit.editingFinished.connect(self._rename_active_layer)

        button_row = self.QtWidgets.QHBoxLayout()
        new_button = self.QtWidgets.QPushButton("New Object")
        new_button.clicked.connect(self._new_segmentation_object)
        duplicate_button = self.QtWidgets.QPushButton("Duplicate")
        duplicate_button.clicked.connect(self._duplicate_active_layer)
        delete_button = self.QtWidgets.QPushButton("Delete")
        delete_button.clicked.connect(self._delete_active_layer)
        merge_button = self.QtWidgets.QPushButton("Merge Selected")
        merge_button.clicked.connect(self._merge_selected_layers)
        for button in [new_button, duplicate_button, delete_button, merge_button]:
            button_row.addWidget(button)

        tool_group = self.QtWidgets.QGroupBox("Mask Editing Tools")
        tool_layout = self.QtWidgets.QGridLayout(tool_group)
        self.brush_size_spin = self.QtWidgets.QSpinBox()
        self.brush_size_spin.setRange(1, 128)
        self.brush_size_spin.setValue(16)
        tools = [
            ("Brush", lambda: self._set_brush_mode(False)),
            ("Erase", lambda: self._set_brush_mode(True)),
            ("Polygon Lasso", lambda: self._log("Polygon lasso: click support is scaffolded; use mask actions for now.")),
            ("Rectangle Select", self._rectangle_select_active),
            ("Magic Wand", lambda: self._log("Magic wand: click on image while Click-to-Segment is enabled.")),
            ("Flood Fill", lambda: self._log("Flood fill uses click prompts in Click-to-Segment mode.")),
            ("Smooth Mask", self._smooth_active_layer),
            ("Expand Mask", self._expand_active_layer),
            ("Contract Mask", self._contract_active_layer),
            ("Fill Holes", self._fill_holes_active_layer),
            ("Feather Edges", self._feather_active_layer),
        ]
        tool_layout.addWidget(self.QtWidgets.QLabel("Brush Size"), 0, 0)
        tool_layout.addWidget(self.brush_size_spin, 0, 1)
        for index, (label, handler) in enumerate(tools, start=1):
            button = self.QtWidgets.QPushButton(label)
            button.clicked.connect(handler)
            tool_layout.addWidget(button, index // 2, index % 2)

        self.layer_tree = self.QtWidgets.QTreeWidget()
        self.layer_tree.setHeaderLabels(["Animation Layer Editor"])
        self.layer_tree.setDragDropMode(self.QtWidgets.QAbstractItemView.InternalMove)
        self.layer_tree.itemChanged.connect(self._layer_tree_item_changed)
        self.layer_tree.itemSelectionChanged.connect(self._layer_tree_selection_changed)

        self.pivot_tree = self.QtWidgets.QTreeWidget()
        self.pivot_tree.setHeaderLabels(["Pivot", "X", "Y"])

        preview_group = self.QtWidgets.QGroupBox("Live Animation Preview")
        preview_layout = self.QtWidgets.QGridLayout(preview_group)
        for index, label in enumerate(["Rotate Head", "Rotate Arm", "Rotate Hand", "Rotate Leg", "Translate Layers", "Scale Layers"]):
            button = self.QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self._log(f"Preview action: {text}"))
            preview_layout.addWidget(button, index // 2, index % 2)

        layout.addWidget(self.interactive_segmentation_checkbox)
        layout.addWidget(self.layer_label_edit)
        layout.addLayout(button_row)
        layout.addWidget(tool_group)
        layout.addWidget(self.layer_tree)
        layout.addWidget(self.pivot_tree)
        layout.addWidget(preview_group)
        self._add_dock("Interactive AI Segmentation", panel, self.QtCore.Qt.RightDockWidgetArea)

    def _build_detection_controls(self) -> None:
        panel = self.QtWidgets.QWidget()
        layout = self.QtWidgets.QVBoxLayout(panel)

        panel_group = self.QtWidgets.QGroupBox("Panel Detection")
        panel_layout = self.QtWidgets.QFormLayout(panel_group)
        self.auto_panels_checkbox = self.QtWidgets.QCheckBox("Automatically Detect Panels")
        self.auto_panels_checkbox.setChecked(True)
        slider_row = self.QtWidgets.QWidget()
        slider_layout = self.QtWidgets.QHBoxLayout(slider_row)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        self.expected_panels_slider = self.QtWidgets.QSlider(self.QtCore.Qt.Horizontal)
        self.expected_panels_slider.setRange(0, 20)
        self.expected_panels_slider.setValue(0)
        self.expected_panels_label = self.QtWidgets.QLabel("Auto")
        self.expected_panels_slider.valueChanged.connect(
            lambda value: self.expected_panels_label.setText("Auto" if value == 0 else str(value))
        )
        slider_layout.addWidget(self.expected_panels_slider, 1)
        slider_layout.addWidget(self.expected_panels_label)
        panel_layout.addRow(self.auto_panels_checkbox)
        panel_layout.addRow("Expected Number of Panels", slider_row)

        char_group = self.QtWidgets.QGroupBox("Character Detection")
        char_layout = self.QtWidgets.QFormLayout(char_group)
        self.expected_characters_default = self.QtWidgets.QSpinBox()
        self.expected_characters_default.setRange(0, 10)
        self.expected_characters_default.setSpecialValueText("Auto")
        self.expected_characters_default.setValue(0)
        char_layout.addRow("Default Expected Characters", self.expected_characters_default)

        review_group = self.QtWidgets.QGroupBox("Detection Review")
        review_layout = self.QtWidgets.QVBoxLayout(review_group)
        self.preview_stage_combo = self.QtWidgets.QComboBox()
        self.preview_stage_combo.addItems(["Original", "Detected Panels", "Detected Characters", "Detected Body Parts", "Background", "Masks"])
        self.preview_stage_combo.currentTextChanged.connect(lambda _value: self._refresh_detection_review())
        self.detection_review_table = self.QtWidgets.QTableWidget(0, 5)
        self.detection_review_table.setHorizontalHeaderLabels(["Type", "ID", "Confidence", "Status", "Expected Characters"])
        self.detection_review_table.horizontalHeader().setStretchLastSection(True)
        review_layout.addWidget(self.preview_stage_combo)
        review_layout.addWidget(self.detection_review_table)

        correction_group = self.QtWidgets.QGroupBox("Interactive Correction Mode")
        correction_layout = self.QtWidgets.QGridLayout(correction_group)
        labels = [
            "Add Panel",
            "Delete Panel",
            "Resize Panel",
            "Split Panel",
            "Merge Panels",
            "Add Character",
            "Delete Character",
            "Split Character Mask",
            "Merge Character Masks",
            "Brush Correction Mask",
        ]
        for index, label in enumerate(labels):
            button = self.QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self._handle_correction_action(text))
            correction_layout.addWidget(button, index // 2, index % 2)

        detect_button = self.QtWidgets.QPushButton("Detect Panels / Characters")
        detect_button.clicked.connect(self._run_detection_preview)
        approve_button = self.QtWidgets.QPushButton("Approve Detection Masks")
        approve_button.clicked.connect(self._approve_detections)
        self.approval_label = self.QtWidgets.QLabel("Approval required before AI body-part processing.")

        layout.addWidget(panel_group)
        layout.addWidget(char_group)
        layout.addWidget(review_group)
        layout.addWidget(correction_group)
        layout.addWidget(detect_button)
        layout.addWidget(approve_button)
        layout.addWidget(self.approval_label)
        layout.addStretch(1)
        self._add_dock("Panel Detection", panel, self.QtCore.Qt.LeftDockWidgetArea)

    def _build_status_bar(self) -> None:
        self.progress_bar = self.QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label = self.QtWidgets.QLabel("Ready")
        self.window.statusBar().addWidget(self.status_label, 1)
        self.window.statusBar().addPermanentWidget(self.progress_bar, 1)

    def _add_dock(self, title: str, widget: Any, area: Any) -> None:
        dock = self.QtWidgets.QDockWidget(title, self.window)
        dock.setObjectName(title.replace(" ", "_"))
        dock.setWidget(widget)
        dock.setAllowedAreas(self.QtCore.Qt.AllDockWidgetAreas)
        self.window.addDockWidget(area, dock)

    def _choose_image(self) -> None:
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            "Choose manga image",
            "",
            "Images (*.jpg *.jpeg *.png *.webp);;All files (*.*)",
        )
        if path:
            self.load_image_path(Path(path))

    def _choose_folder(self) -> None:
        path = self.QtWidgets.QFileDialog.getExistingDirectory(self.window, "Choose input folder")
        if path:
            self.load_image_path(Path(path))

    def _choose_output(self) -> None:
        path = self.QtWidgets.QFileDialog.getExistingDirectory(self.window, "Choose output folder")
        if path:
            self.output_path = Path(path)
            self._set_property("Output", str(self.output_path))
            self._log(f"Output set to {self.output_path}")

    def _start_processing(self, benchmark: bool) -> None:
        if self.input_path is None:
            self.QtWidgets.QMessageBox.warning(self.window, "Input missing", "Load an image or folder before processing.")
            return
        if not self.detections_approved:
            if self.detection_session is None:
                self._run_detection_preview()
            self.QtWidgets.QMessageBox.warning(
                self.window,
                "Approval required",
                "Review and approve panel/character detections before exporting layers.",
            )
            self._log("Export blocked: panel/character detections require user approval.")
            return
        self.progress_bar.setValue(0)
        self.status_label.setText("Running benchmark..." if benchmark else "Processing...")
        self._set_controls_enabled(False)

        worker_wrapper = PipelineWorker(
            self.input_path,
            self.output_path,
            self.config_path,
            self.debug_enabled,
            benchmark,
            self._workflow_options(),
        )
        self.worker = worker_wrapper.obj
        self.worker_thread = self.QtCore.QThread(self.window)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._processing_finished)
        self.worker.failed.connect(self._processing_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _processing_finished(self, panel_count: int) -> None:
        self.status_label.setText("Complete")
        self.progress_bar.setValue(100)
        self._set_property("Panels processed", str(panel_count))
        self._log(f"Processing complete: {panel_count} panel(s).")
        self._set_controls_enabled(True)

    def _processing_failed(self, error: str) -> None:
        self.status_label.setText("Failed")
        self._log(f"ERROR: {error}")
        self.QtWidgets.QMessageBox.critical(self.window, "Processing failed", error)
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for action in self.window.findChildren(self.QtGui.QAction):
            action.setEnabled(enabled)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() == self.QtWidgets.QDialog.Accepted:
            self.batch_size = int(dialog.batch_size.value())
            self.debug_enabled = bool(dialog.debug_checkbox.isChecked())
            self._set_property("Batch size", str(self.batch_size))
            self._set_property("Debug", str(self.debug_enabled))

    def _show_system_info(self) -> None:
        config = load_config(self.config_path)
        runtime = resolve_runtime(config.device)
        lines = [
            f"Device: {runtime.device}",
            f"torch.cuda.is_available(): {torch_cuda_available()}",
            f"Mixed precision: {runtime.mixed_precision}",
            f"PyTorch available: {runtime.torch_available}",
            f"GPU: {runtime.gpu_name or 'not detected'}",
            f"ONNX providers: {', '.join(runtime.onnx_providers) or 'none'}",
        ]
        self._log("\n".join(lines))

    def _run_detection_preview(self) -> None:
        if self.input_path is None:
            self.QtWidgets.QMessageBox.warning(self.window, "Input missing", "Load an image or folder before detection.")
            return
        config = load_config(self.config_path)
        apply_workflow_options(config, self._workflow_options())
        self.detection_session = DetectionWorkflow(config).detect(self.input_path)
        self._apply_panel_expected_character_controls(self.detection_session)
        self.detections_approved = False
        self.approval_label.setText("Review/edit detections, then approve masks.")
        self._draw_detection_overlays(self.detection_session)
        self._populate_detection_review(self.detection_session)
        low_conf = self.detection_session.low_confidence_items
        if low_conf:
            self._log("Low confidence detections require review: " + ", ".join(low_conf))
        self._set_property("Panels detected", str(len(self.detection_session.panels)))

    def _approve_detections(self) -> None:
        if self.detection_session is None:
            self.QtWidgets.QMessageBox.warning(self.window, "No detections", "Run detection before approving.")
            return
        self.detections_approved = True
        self.detection_session.approved_panels = True
        self.detection_session.approved_characters = True
        self.approval_label.setText("Panel and character masks approved. Body-part masks still require semantic/paint approval.")
        self._log("Panel and character detections approved by user.")

    def _draw_detection_overlays(self, session: DetectionSession) -> None:
        for item in self.overlay_items:
            self.image_scene.removeItem(item)
        self.overlay_items.clear()
        panel_pen = self.QtGui.QPen(self.QtGui.QColor("#4e9af1"), 3)
        char_pen = self.QtGui.QPen(self.QtGui.QColor("#f5c542"), 2)
        low_pen = self.QtGui.QPen(self.QtGui.QColor("#ff4d4d"), 3)
        panel_mask_color = self.QtGui.QColor(78, 154, 241, 45)
        char_mask_color = self.QtGui.QColor(245, 197, 66, 60)
        for panel in session.panels:
            bbox = panel.detection.bbox
            pen = panel_pen if panel.detection.confidence >= 0.80 else low_pen
            if panel.detection.mask is not None:
                self._add_mask_overlay(panel.detection.mask, 0, 0, panel_mask_color)
            rect_item = self.image_scene.addRect(bbox.x, bbox.y, bbox.width, bbox.height, pen)
            rect_item.setFlag(self.QtWidgets.QGraphicsItem.ItemIsMovable, True)
            rect_item.setFlag(self.QtWidgets.QGraphicsItem.ItemIsSelectable, True)
            rect_item.setData(0, ("panel", panel.panel_id))
            self.overlay_items.append(rect_item)
            for character in panel.characters:
                cb = character.bbox
                x = bbox.x + cb.x
                y = bbox.y + cb.y
                cpen = char_pen if character.confidence >= 0.80 else low_pen
                if character.mask is not None:
                    self._add_mask_overlay(character.mask, bbox.x, bbox.y, char_mask_color)
                char_item = self.image_scene.addRect(x, y, cb.width, cb.height, cpen)
                char_item.setFlag(self.QtWidgets.QGraphicsItem.ItemIsMovable, True)
                char_item.setFlag(self.QtWidgets.QGraphicsItem.ItemIsSelectable, True)
                char_item.setData(0, ("character", panel.panel_id))
                self.overlay_items.append(char_item)

    def _workflow_options(self) -> dict[str, object]:
        expected_panels = self.expected_panels_slider.value() or None
        expected_characters = self.expected_characters_default.value() or None
        return {
            "auto_detect_panels": self.auto_panels_checkbox.isChecked(),
            "expected_panels": expected_panels,
            "expected_characters": expected_characters,
            "approved_character_masks": self.detections_approved,
            "approved_body_part_masks": False,
            "require_user_approval": True,
        }

    def _add_mask_overlay(self, mask: np.ndarray, offset_x: int, offset_y: int, color: Any) -> None:
        normalized = normalize_mask(mask)
        if normalized.ndim != 2 or int(np.count_nonzero(normalized)) == 0:
            return
        height, width = normalized.shape
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., 0] = color.red()
        rgba[..., 1] = color.green()
        rgba[..., 2] = color.blue()
        rgba[..., 3] = np.where(normalized > 0, color.alpha(), 0).astype(np.uint8)
        image = self.QtGui.QImage(rgba.data, width, height, 4 * width, self.QtGui.QImage.Format_RGBA8888).copy()
        pixmap_item = self.image_scene.addPixmap(self.QtGui.QPixmap.fromImage(image))
        pixmap_item.setOffset(offset_x, offset_y)
        pixmap_item.setZValue(2)
        self.overlay_items.append(pixmap_item)

    def _populate_detection_review(self, session: DetectionSession) -> None:
        self.panel_expected_character_controls.clear()
        self.detection_review_table.setRowCount(0)
        for panel in session.panels:
            self._add_review_row("Panel", panel.panel_id, panel.detection.confidence, panel.expected_characters)
            for index, character in enumerate(panel.characters, start=1):
                self._add_review_row("Character", f"{panel.panel_id}/character_{index:03d}", character.confidence, None)

    def _add_review_row(self, item_type: str, item_id: str, confidence: float, expected_characters: int | None) -> None:
        row = self.detection_review_table.rowCount()
        self.detection_review_table.insertRow(row)
        status = "Approved" if self.detections_approved else ("Needs Review" if confidence < 0.80 else "Review")
        values = [item_type, item_id, f"{confidence:.2f}", status]
        for col, value in enumerate(values):
            item = self.QtWidgets.QTableWidgetItem(value)
            if confidence < 0.50:
                item.setBackground(self.QtGui.QColor("#7f1d1d"))
            elif confidence < 0.80:
                item.setBackground(self.QtGui.QColor("#7c5f00"))
            self.detection_review_table.setItem(row, col, item)
        if item_type == "Panel":
            spin = self.QtWidgets.QSpinBox()
            spin.setRange(0, 10)
            spin.setSpecialValueText("Auto")
            spin.setValue(expected_characters or 0)
            self.panel_expected_character_controls[item_id] = spin
            self.detection_review_table.setCellWidget(row, 4, spin)
        else:
            self.detection_review_table.setItem(row, 4, self.QtWidgets.QTableWidgetItem(""))

    def _refresh_detection_review(self) -> None:
        if self.detection_session is not None:
            self._draw_detection_overlays(self.detection_session)

    def _apply_panel_expected_character_controls(self, session: DetectionSession) -> None:
        for panel in session.panels:
            control = self.panel_expected_character_controls.get(panel.panel_id)
            if control is not None:
                value = int(control.value())
                panel.expected_characters = value or None

    def _handle_correction_action(self, action: str) -> None:
        if self.detection_session is None:
            self._log(f"{action}: run detection first.")
            return
        if action == "Add Panel":
            self._add_manual_panel()
        elif action == "Delete Panel":
            self._delete_selected_overlays("panel")
        elif action == "Add Character":
            self._add_manual_character()
        elif action == "Delete Character":
            self._delete_selected_overlays("character")
        elif action == "Brush Correction Mask":
            self.brush_correction_enabled = not self.brush_correction_enabled
            self._log(f"Brush correction mode {'enabled' if self.brush_correction_enabled else 'disabled'}.")
        else:
            self._log(f"{action}: select overlays in preview; current operation is recorded for manual correction.")
        self.detections_approved = False
        self.approval_label.setText("Corrections changed detections; approval required.")

    def _add_manual_panel(self) -> None:
        if self.detection_session is None:
            return
        rect = self.image_scene.sceneRect()
        width = max(1, int(rect.width() * 0.5))
        height = max(1, int(rect.height() * 0.5))
        x = int(rect.x() + rect.width() * 0.25)
        y = int(rect.y() + rect.height() * 0.25)
        mask = np.zeros((int(rect.height()), int(rect.width())), dtype=np.uint8)
        mask[y : y + height, x : x + width] = 255
        panel_id = f"panel_{len(self.detection_session.panels) + 1:03d}"
        self.detection_session.panels.append(
            PanelDraft(panel_id=panel_id, detection=Detection("panel", BoundingBox(x, y, width, height), 0.50, mask=mask, label="manual_panel"))
        )
        self._draw_detection_overlays(self.detection_session)
        self._populate_detection_review(self.detection_session)
        self._log(f"Added manual panel {panel_id}.")

    def _add_manual_character(self) -> None:
        if self.detection_session is None or not self.detection_session.panels:
            return
        panel = self.detection_session.panels[0]
        pb = panel.detection.bbox
        width = max(24, int(pb.width * 0.25))
        height = max(32, int(pb.height * 0.45))
        x = max(0, int(pb.width * 0.375))
        y = max(0, int(pb.height * 0.25))
        mask = np.zeros((pb.height, pb.width), dtype=np.uint8)
        mask[y : y + height, x : x + width] = 255
        panel.characters.append(Detection("character", BoundingBox(x, y, width, height), 0.50, mask=mask, label="manual_character"))
        self._draw_detection_overlays(self.detection_session)
        self._populate_detection_review(self.detection_session)
        self._log(f"Added manual character to {panel.panel_id}.")

    def _delete_selected_overlays(self, item_type: str) -> None:
        selected = [item for item in self.image_scene.selectedItems() if item.data(0) and item.data(0)[0] == item_type]
        for item in selected:
            self.image_scene.removeItem(item)
            if item in self.overlay_items:
                self.overlay_items.remove(item)
        self._log(f"Deleted {len(selected)} selected {item_type} overlay(s).")

    def _toggle_interactive_segmentation(self, enabled: bool) -> None:
        self.interactive_segmentation_enabled = enabled
        self._log("Click-to-segment enabled. Left click adds positive prompts; right click adds negative prompts." if enabled else "Click-to-segment disabled.")

    def _image_mouse_press_event(self, event: Any) -> None:
        if not self.interactive_segmentation_enabled or self.segmentation_session is None:
            self._original_viewport_mouse_press(event)
            return
        scene_point = self.image_view.mapToScene(event.position().toPoint())
        x, y = int(scene_point.x()), int(scene_point.y())
        if self.brush_correction_enabled and self.segmentation_session.active_layer is not None:
            erase = event.button() == self.QtCore.Qt.RightButton or self._brush_erase
            self.segmentation_session.brush(x, y, self.brush_size_spin.value(), erase=erase)
            self._refresh_segmentation_overlays()
            self._refresh_layer_tree()
            self._refresh_pivot_tree()
            self._log(("Erased" if erase else "Painted") + f" mask at ({x}, {y}).")
            return
        if event.button() == self.QtCore.Qt.LeftButton:
            layer = self.segmentation_session.add_prompt(x, y, positive=True)
            self._log(f"Positive prompt at ({x}, {y}) -> {layer.label} ({layer.confidence:.2f})")
        elif event.button() == self.QtCore.Qt.RightButton:
            layer = self.segmentation_session.add_prompt(x, y, positive=False)
            self._log(f"Negative prompt at ({x}, {y}) refined {layer.label}")
        else:
            self._original_viewport_mouse_press(event)
            return
        self.layer_label_edit.setText(layer.label)
        self._refresh_segmentation_overlays()
        self._refresh_layer_tree()
        self._refresh_pivot_tree()

    def _new_segmentation_object(self) -> None:
        if self.segmentation_session is None:
            self._log("Load an image before creating segmentation layers.")
            return
        self.segmentation_session.active_layer_id = None
        self._log("New object mode: left click the object to segment.")

    def _rename_active_layer(self) -> None:
        if self.segmentation_session is None:
            return
        label = self.layer_label_edit.text().strip()
        if label:
            self.segmentation_session.rename_active(label)
            self._refresh_layer_tree()

    def _duplicate_active_layer(self) -> None:
        if self.segmentation_session is None:
            return
        if self.segmentation_session.duplicate_active() is not None:
            self._refresh_layer_tree()
            self._refresh_segmentation_overlays()
            self._refresh_pivot_tree()

    def _delete_active_layer(self) -> None:
        if self.segmentation_session is None:
            return
        self.segmentation_session.delete_active()
        self._refresh_layer_tree()
        self._refresh_segmentation_overlays()
        self._refresh_pivot_tree()

    def _merge_selected_layers(self) -> None:
        if self.segmentation_session is None:
            return
        layer_ids = []
        for item in self.layer_tree.selectedItems():
            layer_id = item.data(0, self.QtCore.Qt.UserRole)
            if layer_id:
                layer_ids.append(layer_id)
        if self.segmentation_session.merge_layers(layer_ids, "Merged Layer") is not None:
            self._refresh_layer_tree()
            self._refresh_segmentation_overlays()
            self._refresh_pivot_tree()

    def _layer_tree_selection_changed(self) -> None:
        if self.segmentation_session is None:
            return
        selected = self.layer_tree.selectedItems()
        if not selected:
            return
        layer_id = selected[0].data(0, self.QtCore.Qt.UserRole)
        if layer_id:
            self.segmentation_session.active_layer_id = layer_id
            layer = self.segmentation_session.active_layer
            if layer:
                self.layer_label_edit.setText(layer.label)
                self._refresh_pivot_tree()

    def _layer_tree_item_changed(self, item: Any, column: int) -> None:
        if self.segmentation_session is None or column != 0:
            return
        layer_id = item.data(0, self.QtCore.Qt.UserRole)
        if not layer_id:
            return
        layer = next((entry for entry in self.segmentation_session.layers if entry.layer_id == layer_id), None)
        if layer is None:
            return
        layer.label = item.text(0)
        layer.visible = item.checkState(0) == self.QtCore.Qt.Checked
        self._refresh_segmentation_overlays()

    def _set_brush_mode(self, erase: bool) -> None:
        self.interactive_segmentation_enabled = True
        self.interactive_segmentation_checkbox.setChecked(True)
        self.brush_correction_enabled = True
        self._log("Erase brush active." if erase else "Brush add mode active.")
        self._brush_erase = erase

    def _rectangle_select_active(self) -> None:
        if self.segmentation_session is None or self.segmentation_session.active_layer is None:
            return
        rect = self.image_scene.sceneRect()
        bbox = BoundingBox(int(rect.width() * 0.25), int(rect.height() * 0.25), int(rect.width() * 0.5), int(rect.height() * 0.5))
        self.segmentation_session.rectangle_select(bbox, add=True)
        self._refresh_segmentation_overlays()
        self._refresh_layer_tree()

    def _smooth_active_layer(self) -> None:
        if self.segmentation_session:
            self.segmentation_session.smooth_active()
            self._refresh_segmentation_overlays()

    def _expand_active_layer(self) -> None:
        if self.segmentation_session:
            self.segmentation_session.expand_active(3)
            self._refresh_segmentation_overlays()

    def _contract_active_layer(self) -> None:
        if self.segmentation_session:
            self.segmentation_session.contract_active(3)
            self._refresh_segmentation_overlays()

    def _fill_holes_active_layer(self) -> None:
        if self.segmentation_session:
            self.segmentation_session.fill_holes_active()
            self._refresh_segmentation_overlays()

    def _feather_active_layer(self) -> None:
        if self.segmentation_session:
            self.segmentation_session.feather_active(3)
            self._refresh_segmentation_overlays()

    def _refresh_segmentation_overlays(self) -> None:
        for item in self.segmentation_overlay_items:
            self.image_scene.removeItem(item)
        self.segmentation_overlay_items.clear()
        if self.segmentation_session is None:
            return
        colors = [
            self.QtGui.QColor(46, 204, 113, 90),
            self.QtGui.QColor(155, 89, 182, 90),
            self.QtGui.QColor(231, 76, 60, 90),
            self.QtGui.QColor(241, 196, 15, 90),
            self.QtGui.QColor(52, 152, 219, 90),
        ]
        for index, layer in enumerate(self.segmentation_session.layers):
            if not layer.visible:
                continue
            before_count = len(self.overlay_items)
            self._add_mask_overlay(layer.mask, 0, 0, colors[index % len(colors)])
            new_items = self.overlay_items[before_count:]
            for item in new_items:
                item.setZValue(5 + index)
                self.segmentation_overlay_items.append(item)
            self.overlay_items = self.overlay_items[:before_count]

    def _refresh_layer_tree(self) -> None:
        if not hasattr(self, "layer_tree"):
            return
        self.layer_tree.blockSignals(True)
        self.layer_tree.clear()
        panel_item = self.QtWidgets.QTreeWidgetItem(["Panel 1"])
        panel_item.setFlags(panel_item.flags() | self.QtCore.Qt.ItemIsDropEnabled)
        self.layer_tree.addTopLevelItem(panel_item)
        if self.segmentation_session is not None:
            character_roots: dict[str, Any] = {}
            for layer in self.segmentation_session.layers:
                parent_label = "Speech Bubbles" if layer.label == "Speech Bubble" else "Background" if layer.label == "Background" else "Character 1"
                if parent_label not in character_roots:
                    root = self.QtWidgets.QTreeWidgetItem([parent_label])
                    root.setFlags(root.flags() | self.QtCore.Qt.ItemIsDropEnabled)
                    panel_item.addChild(root)
                    character_roots[parent_label] = root
                item = self.QtWidgets.QTreeWidgetItem([layer.label])
                item.setData(0, self.QtCore.Qt.UserRole, layer.layer_id)
                item.setFlags(item.flags() | self.QtCore.Qt.ItemIsEditable | self.QtCore.Qt.ItemIsDragEnabled | self.QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, self.QtCore.Qt.Checked if layer.visible else self.QtCore.Qt.Unchecked)
                character_roots[parent_label].addChild(item)
        panel_item.setExpanded(True)
        self.layer_tree.expandAll()
        self.layer_tree.blockSignals(False)

    def _refresh_pivot_tree(self) -> None:
        if not hasattr(self, "pivot_tree"):
            return
        self.pivot_tree.clear()
        if self.segmentation_session is None or self.segmentation_session.active_layer is None:
            return
        for pivot in self.segmentation_session.active_layer.pivots:
            item = self.QtWidgets.QTreeWidgetItem([pivot.name, f"{pivot.x:.1f}", f"{pivot.y:.1f}"])
            self.pivot_tree.addTopLevelItem(item)

    def _populate_project_tree(self, root_path: Path, images: list[Path]) -> None:
        self.project_tree.clear()
        root_item = self.QtWidgets.QTreeWidgetItem([str(root_path)])
        self.project_tree.addTopLevelItem(root_item)
        for image_path in images:
            root_item.addChild(self.QtWidgets.QTreeWidgetItem([image_path.name]))
        root_item.setExpanded(True)

    def _log(self, message: str) -> None:
        self.console.appendPlainText(message)

    def _set_property(self, key: str, value: str) -> None:
        for row in range(self.properties_table.rowCount()):
            if self.properties_table.item(row, 0) and self.properties_table.item(row, 0).text() == key:
                self.properties_table.setItem(row, 1, self.QtWidgets.QTableWidgetItem(value))
                return
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)
        self.properties_table.setItem(row, 0, self.QtWidgets.QTableWidgetItem(key))
        self.properties_table.setItem(row, 1, self.QtWidgets.QTableWidgetItem(value))


def gui_smoke_test(sample_input: Path | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    """Validate PySide6 GUI launch, optional image loading, and optional processing."""

    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        app = _ensure_app()
        window = MangaAnimatorPrepMainWindow()
        window.show()
        app.processEvents()
        result: dict[str, Any] = {"status": "working", "gui": "PySide6", "image_loaded": False, "processing_triggered": False}
        if sample_input is not None:
            result["image_loaded"] = window.load_image_path(sample_input)
            app.processEvents()
        if sample_input is not None and output_dir is not None:
            window._run_detection_preview()
            window._approve_detections()
            app.processEvents()
            panel_count = window.run_processing_blocking(sample_input, output_dir, benchmark=False)
            app.processEvents()
            result["processing_triggered"] = True
            result["panels_processed"] = panel_count
        window.close()
        app.processEvents()
        return result
    except Exception as exc:  # pragma: no cover - explicit diagnostics
        return {"status": "broken", "gui": "PySide6", "error": str(exc)}


def launch_gui(config_path: Path | None = None) -> None:
    app = _ensure_app()
    window = MangaAnimatorPrepMainWindow(config_path)
    window.show()
    app.exec()


def apply_workflow_options(config: Any, options: dict[str, object]) -> None:
    config.workflow.auto_detect_panels = bool(options.get("auto_detect_panels", True))
    config.workflow.expected_panels = options.get("expected_panels")  # type: ignore[assignment]
    config.workflow.expected_characters = options.get("expected_characters")  # type: ignore[assignment]
    config.workflow.approved_character_masks = bool(options.get("approved_character_masks", False))
    config.workflow.approved_body_part_masks = bool(options.get("approved_body_part_masks", False))
    config.workflow.require_user_approval = bool(options.get("require_user_approval", True))

