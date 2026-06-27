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
    assert window.expected_panels_slider.minimum() == 0
    assert window.expected_panels_slider.maximum() == 20
    assert window.expected_panels_label.text() == "Auto"
    assert window.expected_characters_default.maximum() == 10
    assert window.detection_review_table.sizePolicy().verticalPolicy() == window.QtWidgets.QSizePolicy.Expanding
    assert window.detection_review_table.minimumHeight() >= 220
    assert window.detection_review_table.verticalScrollBarPolicy() == window.QtCore.Qt.ScrollBarAsNeeded
    assert window.load_image_path(sample) is True
    window._run_detection_preview()
    assert window.detection_session is not None
    assert window.overlay_items
    assert window.detection_review_table.rowCount() > 0
    window._approve_detections()
    assert window.detections_approved is True
    window.close()
    app.processEvents()


def test_gui_body_part_table_and_boundary_editor(tmp_path: Path) -> None:
    app = _ensure_app()
    sample = tmp_path / "sample.png"
    create_sample(sample)
    window = MangaAnimatorPrepMainWindow()
    assert window.load_image_path(sample) is True
    assert window.body_part_table.rowCount() >= 10
    window.body_part_search.setText("Head")
    window._filter_body_part_table()
    visible_rows = [row for row in range(window.body_part_table.rowCount()) if not window.body_part_table.isRowHidden(row)]
    assert visible_rows
    window.body_part_table.selectRow(visible_rows[0])
    window._edit_body_part("Head")
    window.part_x_spin.setValue(20)
    window.part_y_spin.setValue(20)
    window.part_w_spin.setValue(40)
    window.part_h_spin.setValue(50)
    window._auto_resegment_selected_part()
    assert window.body_part_state["Head"]["status"] == "Visible"
    assert window.segmentation_session is not None
    assert any(layer.label == "Head" for layer in window.segmentation_session.layers)
    window.close()
    app.processEvents()

