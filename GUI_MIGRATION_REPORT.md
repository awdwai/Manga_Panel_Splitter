# GUI Migration Report

## Summary

The GUI stack has been migrated from Tkinter to **PySide6**. There is no Tkinter fallback.

The migration preserves the existing business logic:

- processing still runs through `MangaAnimatorPipeline`
- export logic is unchanged
- benchmark/report generation is unchanged
- image loading uses the existing supported file discovery and image utilities

## Implemented PySide6 components

| Requirement | Status | Implementation |
|---|---|---|
| Main Window | Complete | `MangaAnimatorPrepMainWindow` wraps `QMainWindow`. |
| Dockable Panels | Complete | `QDockWidget` panels for Project Explorer, Properties, and Processing Console. |
| Dark Theme | Complete | Application stylesheet applied to main window, docks, menus, tables, console, and progress bar. |
| Image Viewer | Complete | Central `QGraphicsView` + `QGraphicsScene` loads and displays selected images. |
| Project Explorer | Complete | `QTreeWidget` lists loaded image/folder contents. |
| Properties Panel | Complete | `QTableWidget` shows input, output, image count, first image, and processed panel count. |
| Processing Console | Complete | `QPlainTextEdit` records runtime messages. |
| Progress Bar | Complete | Status bar `QProgressBar` updates during processing. |
| Settings Dialog | Complete | `QDialog` exposes debug-output and batch-size settings. |

## Files changed

- `MangaAnimatorPrep/gui.py`
  - Replaced Tkinter implementation with PySide6.
  - Added `QMainWindow`, dock widgets, image viewer, project explorer, properties table, console, progress bar, and settings dialog.
  - Added background processing via `QThread`/`QObject` worker.
  - Added offscreen-capable GUI smoke verification.
- `MangaAnimatorPrep/main.py`
  - Updated `gui --smoke-test` to validate PySide6.
  - Added `--smoke-input` and `--smoke-output` so CI can verify image loading and processing trigger.
- `requirements.txt`
  - Added required dependency: `PySide6`.
- `tests/test_gui.py`
  - Added PySide6 GUI smoke test that loads an image and triggers processing.
  - Added settings dialog construction regression test.
- Documentation/audit files updated to remove Tkinter as the current GUI stack.

## Issues found and fixed during migration

### 1. Missing PySide6 dependency

Cause:

- The previous GUI used Tkinter and `requirements.txt` did not include PySide6.

Fix:

- Added `PySide6` to `requirements.txt`.
- Installed PySide6 in the verification environment with `python3 -m pip install PySide6`.

Test:

- PySide6 imports successfully.

### 2. Missing Linux Qt runtime library

Cause:

- PySide6 initially failed in the cloud environment with:

```text
libEGL.so.1: cannot open shared object file: No such file or directory
```

Fix:

- Installed the required Linux runtime library:

```bash
sudo apt-get install -y libegl1
```

Test:

- Offscreen PySide6 GUI smoke test launches.

### 3. Settings dialog parent type error

Cause:

- `SettingsDialog` passed the Python wrapper object instead of the underlying `QMainWindow` as the `QDialog` parent.

Error:

```text
TypeError: 'PySide6.QtWidgets.QDialog.__init__' called with wrong argument types
```

Fix:

- Changed parent from `parent` to `parent.window`.

Test:

- Added `test_pyside6_settings_dialog_constructs`.

## Verification commands

```bash
python3 -m compileall MangaAnimatorPrep scripts tests
python3 -m pip check
QT_QPA_PLATFORM=offscreen python3 -m pytest -q
python3 scripts/create_sample_data.py
QT_QPA_PLATFORM=offscreen python3 -m MangaAnimatorPrep.main gui \
  --smoke-test \
  --smoke-input sample_data/sample_page.png \
  --smoke-output gui_migration_output
```

## Verification results

```text
No broken requirements found.
11 passed in 3.00s
```

GUI smoke result:

```text
{
    'status': 'working',
    'gui': 'PySide6',
    'image_loaded': True,
    'processing_triggered': True,
    'panels_processed': 3
}
```

## Remaining limitations

- The GUI is PySide6 and functional, but still wraps the existing heuristic processing pipeline.
- The GUI verification in this cloud machine uses `QT_QPA_PLATFORM=offscreen` because no real desktop display is attached.
- The message `This plugin does not support propagateSizeHints()` appears during offscreen verification. It is emitted by the Qt offscreen platform plugin and did not prevent launch, loading, or processing.

