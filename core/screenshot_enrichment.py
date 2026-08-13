from __future__ import annotations

import threading
from pathlib import Path

from core.accessibility_text import (
    is_useful_accessibility_text,
    normalize_accessibility_text,
)
from core.app_settings import get_capture_settings
from core.image_embeddings import embed_image
from core.ocr import extract_text

_cache: dict[str, tuple[int, int, str, list[float] | None, str | None, bool, bool]] = {}
_accessibility_cache: dict[str, tuple[int, int, str]] = {}
_cache_lock = threading.Lock()
_cache_limit = 512


def merge_ocr_text(*values: str | None) -> str:
    seen = set()
    lines = []
    for value in values:
        for line in str(value or "").splitlines():
            text = " ".join(line.split()).strip()
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                lines.append(text)
    return "\n".join(lines)[:4000]


def remember_accessibility_text(path: Path, text: str) -> None:
    stat = path.stat()
    with _cache_lock:
        _accessibility_cache[str(path)] = (
            stat.st_mtime_ns,
            stat.st_size,
            normalize_accessibility_text(text),
        )
        while len(_accessibility_cache) > _cache_limit:
            stale = next(iter(_accessibility_cache))
            _accessibility_cache.pop(stale, None)
            _cache.pop(stale, None)


def _captured_accessibility_text(path: Path, stat) -> str:
    with _cache_lock:
        cached = _accessibility_cache.get(str(path))
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return cached[2]
    return ""


def enrich_screenshot(
    path: Path,
    *,
    include_image_embedding: bool = True,
) -> tuple[str, list[float] | None, str | None]:
    stat = path.stat()
    key = str(path)
    settings = get_capture_settings()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            ocr_cached = cached[5]
            embeddings_cached = cached[6]
            # Feature flags are part of cache validity: enabling OCR or image
            # embeddings later must enrich the file instead of returning gaps.
            if (not settings["ocr_enabled"] or ocr_cached) and (
                not settings["image_embeddings_enabled"] or not include_image_embedding or embeddings_cached
            ):
                return (
                    cached[2] if settings["ocr_enabled"] else "",
                    cached[3] if settings["image_embeddings_enabled"] and include_image_embedding else None,
                    cached[4] if settings["image_embeddings_enabled"] and include_image_embedding else None,
                )

    accessibility_text = _captured_accessibility_text(path, stat)
    should_run_ocr = settings["ocr_enabled"] and not is_useful_accessibility_text(accessibility_text)
    ocr_text = extract_text(path) if should_run_ocr else ""
    captured_text = merge_ocr_text(accessibility_text, ocr_text)
    should_embed_image = settings["image_embeddings_enabled"] and include_image_embedding
    image_embedding, image_embedding_model = (embed_image(path) if should_embed_image else (None, None))
    result = (captured_text, image_embedding, image_embedding_model)
    with _cache_lock:
        _cache[key] = (
            stat.st_mtime_ns,
            stat.st_size,
            *result,
            bool(settings["ocr_enabled"]),
            bool(should_embed_image),
        )
        while len(_cache) > _cache_limit:
            stale = next(iter(_cache))
            _cache.pop(stale)
            _accessibility_cache.pop(stale, None)
    return result
