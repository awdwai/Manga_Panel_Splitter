from __future__ import annotations

from MangaAnimatorPrep.gui import gui_smoke_test


def test_gui_smoke_test_is_headless_safe() -> None:
    result = gui_smoke_test()
    assert result["status"] in {"working", "headless"}

