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

