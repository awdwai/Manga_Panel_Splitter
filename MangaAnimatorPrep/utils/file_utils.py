"""Filesystem helpers."""

from __future__ import annotations

from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_images(path: Path) -> list[Path]:
    """Return image files from one file or a directory tree."""

    if path.is_file():
        return [path] if path.suffix.lower() in IMAGE_EXTENSIONS else []
    if not path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def numbered_name(prefix: str, index: int, suffix: str = ".png") -> str:
    return f"{prefix}_{index:03d}{suffix}"

