"""Small in-process cache for immutable render-time file artifacts."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from threading import RLock
from typing import Callable, TypeVar


T = TypeVar("T")
_MAX_ENTRIES = 512
_CACHE: OrderedDict[tuple[str, int, int], object] = OrderedDict()
_LOCK = RLock()


def get_or_load(path: str | Path, loader: Callable[[Path], T]) -> T:
    """Return a cached per-file value, reloading when mtime or size changes."""
    resolved = Path(path).resolve()
    stat = resolved.stat()
    key = (str(resolved), stat.st_mtime_ns, stat.st_size)

    with _LOCK:
        if key in _CACHE:
            value = _CACHE.pop(key)
            _CACHE[key] = value
            return value  # type: ignore[return-value]

    value = loader(resolved)
    with _LOCK:
        _CACHE[key] = value
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return value


def clear() -> None:
    """Clear cached artifacts. Intended for deterministic test isolation."""
    with _LOCK:
        _CACHE.clear()
