"""Lazy model cache for heavyweight inference backends."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    """Cached model object and load metadata."""

    value: T
    load_seconds: float


class ModelCache:
    """Process-local model cache that avoids reloading models between panels."""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry[object]] = {}
        self._lock = threading.Lock()

    def get_or_load(self, key: str, loader: Callable[[], T]) -> CacheEntry[T]:
        with self._lock:
            if key in self._entries:
                return self._entries[key]  # type: ignore[return-value]
            start = time.perf_counter()
            LOGGER.info("Loading model backend: %s", key)
            value = loader()
            entry: CacheEntry[T] = CacheEntry(value=value, load_seconds=time.perf_counter() - start)
            self._entries[key] = entry
            return entry

    def has(self, key: str) -> bool:
        return key in self._entries

    def load_times(self) -> dict[str, float]:
        return {key: entry.load_seconds for key, entry in self._entries.items()}

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


GLOBAL_MODEL_CACHE = ModelCache()

