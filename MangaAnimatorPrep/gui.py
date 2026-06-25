"""PySide6 desktop GUI for MangaAnimatorPrep."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from MangaAnimatorPrep.config import load_config
from MangaAnimatorPrep.pipeline import MangaAnimatorPipeline
from MangaAnimatorPrep.utils.file_utils import list_images
from MangaAnimatorPrep.utils.gpu import resolve_runtime, torch_cuda_available
from MangaAnimatorPrep.utils.image_utils import load_image


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

    def __init__(self, input_path: Path, output_path: Path, config_path: Path | None, debug: bool, benchmark: bool) -> None:
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
        pixmap = self.QtGui.QPixmap(str(first_image))
        if pixmap.isNull():
            array = load_image(first_image)
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
        return True

    def run_processing_blocking(self, input_path: Path, output_path: Path, benchmark: bool = False) -> int:
        config = load_config(self.config_path)
        config.output.debug = self.debug_enabled
        config.device.batch_size = self.batch_size
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
        self.progress_bar.setValue(0)
        self.status_label.setText("Running benchmark..." if benchmark else "Processing...")
        self._set_controls_enabled(False)

        worker_wrapper = PipelineWorker(self.input_path, self.output_path, self.config_path, self.debug_enabled, benchmark)
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

