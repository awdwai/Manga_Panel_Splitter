from __future__ import annotations

from pathlib import Path

from MangaAnimatorPrep.gui import MangaAnimatorPrepMainWindow, SettingsDialog, _ensure_app, gui_smoke_test
from scripts.create_sample_data import create_sample


def test_pyside6_gui_smoke_test_loads_and_processes(tmp_path: Path) -> None:
    sample = tmp_path / "sample.png"
    output = tmp_path / "gui_output"
    create_sample(sample)
    result = gui_smoke_test(sample, output)
    assert result["status"] == "working"
    assert result["gui"] == "PySide6"
    assert result["image_loaded"] is True
    assert result["processing_triggered"] is True
    assert result["panels_processed"] >= 1
    assert (output / "panel_001").exists()


def test_pyside6_settings_dialog_constructs() -> None:
    app = _ensure_app()
    window = MangaAnimatorPrepMainWindow()
    dialog = SettingsDialog(window)
    assert dialog.dialog.windowTitle() == "Settings"
    window.close()
    app.processEvents()


def test_gui_detection_controls_preview_and_approval(tmp_path: Path) -> None:
    app = _ensure_app()
    sample = tmp_path / "sample.png"
    create_sample(sample)
    window = MangaAnimatorPrepMainWindow()
    assert window.auto_panels_checkbox.text() == "Automatically Detect Panels"
    assert window.expected_panels_combo.count() == 21
    assert window.expected_characters_combo.count() == 11
    assert window.load_image_path(sample) is True
    window._run_detection_preview()
    assert window.detection_session is not None
    assert window.overlay_items
    window._approve_detections()
    assert window.detections_approved is True
    window.close()
    app.processEvents()

