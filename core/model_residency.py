"""Text model residency for the local assistant.

Startup (API): pin the local Ollama text model.
Capture: accessibility text and OCR run without loading a vision model.

Persists to <data>/model_residency.json. Gateway reads policy via keep_alive_for().
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Literal

import psutil

try:
    from core.paths import get_data_dir
except ImportError:
    from paths import get_data_dir

TEXT_MODEL = "qwen3:8b"
VL_MODEL = "qwen3-vl:4b"

VisionPolicy = Literal["idle", "pinned", "on_demand"]

_GB = 1024**3
_EST_VL = 3.5 * _GB
_FREE_FLOOR = 3.5 * _GB
_OCR_FLOOR = 0.5 * _GB
_LIGHT_FLOOR = 1.0 * _GB
_TEXT_FLOOR = 1.5 * _GB
# Windows reports commit charge beyond physical RAM as swap. Near-exhaustion is
# what raises "paging file is too small" (os error 1455) and ONNX bad_alloc,
# even while physical RAM still looks free.
_COMMIT_PRESSURE_PCT = 75.0
_PRESSURE_INTERVAL_S = 30
_PS_CACHE_TTL_S = 5.0

KEEP_ALIVE_PINNED = "1h"
KEEP_ALIVE_VL_EPHEMERAL = "5m"
KEEP_ALIVE_UNLOAD = 0

_OLLAMA = "http://127.0.0.1:11434"
_STATE_NAME = "model_residency.json"

_policy: VisionPolicy = "idle"
_monitor_stop = threading.Event()
_monitor_thread: threading.Thread | None = None
_lock = threading.Lock()
_ps_cache: tuple[float, set[str]] | None = None
_last_warm_attempt_mono = 0.0
_WARM_RETRY_SECS = 120.0


def _state_path() -> Path:
    return get_data_dir() / _STATE_NAME


def _available() -> int:
    return int(psutil.virtual_memory().available)


def _mb(n: int) -> int:
    return round(n / (1024 * 1024))


def _can_pin_vision(available: int | None = None) -> bool:
    """True if VL plus a free-RAM floor still fits."""
    free = _available() if available is None else available
    return free >= _EST_VL + _FREE_FLOOR


def _commit_pressured() -> bool:
    try:
        return psutil.swap_memory().percent >= _COMMIT_PRESSURE_PCT
    except Exception:
        return False


def _ollama_loaded_models() -> set[str]:
    """Names currently resident in Ollama (/api/ps). Cached briefly."""
    global _ps_cache
    now = time.monotonic()
    if _ps_cache and (now - _ps_cache[0]) < _PS_CACHE_TTL_S:
        return _ps_cache[1]
    names: set[str] = set()
    try:
        req = urllib.request.Request(f"{_OLLAMA}/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        for item in data.get("models") or []:
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                names.add(name)
    except Exception:
        names = set(_ps_cache[1]) if _ps_cache else set()
    _ps_cache = (now, names)
    return names


def text_model_loaded(model: str = TEXT_MODEL) -> bool:
    """True when the chat/summary model is already resident in Ollama."""
    loaded = _ollama_loaded_models()
    target = model.casefold()
    for name in loaded:
        key = name.casefold()
        if key == target or key.startswith(target):
            return True
    return False


def can_cold_load_text(available: int | None = None) -> bool:
    """True if free memory is enough to *load* the text model from scratch."""
    free = _available() if available is None else available
    return free >= _TEXT_FLOOR and not _commit_pressured()


def can_load_text(available: int | None = None) -> bool:
    """True if text inference is safe to attempt.

    Free-RAM floors only apply to cold loads. Once the model is already resident
    (as during chat), summarizer/distil/catch-up must not defer just because the
    occupied model left little *available* RAM — that memory is already paid for.
    """
    if text_model_loaded():
        return True
    return can_cold_load_text(available)


def can_load_light(available: int | None = None) -> bool:
    """True if a small torch model (MiniLM router, CLIP) can load."""
    free = _available() if available is None else available
    return free >= _LIGHT_FLOOR and not _commit_pressured()


def can_run_ocr(available: int | None = None) -> bool:
    """True unless memory is already in the allocation-failure range."""
    free = _available() if available is None else available
    return free >= _OCR_FLOOR and not _commit_pressured()


def load_residency() -> dict:
    global _policy
    path = _state_path()
    if not path.exists():
        _policy = "idle"
        return {"vision": _policy}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[residency] read failed: {e}")
        _policy = "idle"
        return {"vision": _policy}

    vision = data.get("vision") or data.get("mode")  # mode: legacy dual/single
    if vision == "dual":
        vision = "pinned"
    elif vision == "single":
        vision = "on_demand"
    if vision not in ("idle", "pinned", "on_demand"):
        vision = "idle"
    _policy = vision  # type: ignore[assignment]
    data["vision"] = _policy
    return data


def _persist(vision: VisionPolicy, **extra: Any) -> dict:
    global _policy
    _policy = vision
    payload = {
        "vision": vision,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "available_ram_mb": _mb(_available()),
        **extra,
    }
    _state_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[residency] vision={vision}  free~{payload['available_ram_mb']}MB")
    return payload


def keep_alive_for(model: str) -> str | int:
    if "vl" not in (model or "").lower():
        return KEEP_ALIVE_PINNED
    if _policy == "pinned":
        return KEEP_ALIVE_PINNED
    if _policy == "on_demand":
        return KEEP_ALIVE_VL_EPHEMERAL
    return KEEP_ALIVE_UNLOAD


def _ollama_post(path: str, body: dict, timeout: float = 90) -> None:
    req = urllib.request.Request(
        f"{_OLLAMA}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def _warm(model: str, keep_alive: str | int = KEEP_ALIVE_PINNED, timeout: float = 90) -> None:
    # Non-empty prompt: empty prompt hangs on some Ollama builds
    print(f"[residency] warm {model} (keep_alive={keep_alive!r})")
    _ollama_post(
        "/api/generate",
        {"model": model, "prompt": "ping", "stream": False, "keep_alive": keep_alive},
        timeout=timeout,
    )
    # Bust the /api/ps cache so text_model_loaded() sees the new resident model.
    global _ps_cache
    _ps_cache = None


def ensure_text_model(*, force: bool = False) -> bool:
    """
    Best-effort: make the chat/summary model resident in Ollama.

    Prefers trying a load over a hard free-RAM skip. A static floor often
    strands the app (summarizer/distil forever deferred) even when Ollama
    could still load the model. Retries are rate-limited unless force=True.
    """
    global _last_warm_attempt_mono
    if text_model_loaded(TEXT_MODEL):
        return True
    # Extreme commit pressure usually means Windows will page-fault hard.
    if _commit_pressured() and not force:
        return False
    now = time.monotonic()
    with _lock:
        if not force and (now - _last_warm_attempt_mono) < _WARM_RETRY_SECS:
            return False
        _last_warm_attempt_mono = now
    free = _available()
    if free < _TEXT_FLOOR:
        print(
            f"[residency] trying text warm below floor "
            f"(free~{free / _GB:.1f}GB < {_TEXT_FLOOR / _GB:.1f}GB) — "
            "better than leaving the model unloaded"
        )
    try:
        _warm(TEXT_MODEL, timeout=120)
    except Exception as exc:
        print(f"[residency] text warm failed: {exc}")
        return False
    return text_model_loaded(TEXT_MODEL)


def _unload_vision() -> None:
    print(f"[residency] unload {VL_MODEL}")
    try:
        _ollama_post(
            "/api/generate",
            {
                "model": VL_MODEL,
                "prompt": "ping",
                "stream": False,
                "keep_alive": KEEP_ALIVE_UNLOAD,
            },
            timeout=30,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[residency] unload failed: {e}")


def _stop_monitor() -> None:
    global _monitor_thread
    _monitor_stop.set()
    _monitor_thread = None


def _pressure_loop() -> None:
    """While vision is pinned, demote to on-demand if free RAM collapses."""
    while not _monitor_stop.wait(_PRESSURE_INTERVAL_S):
        with _lock:
            if _policy != "pinned":
                return
            free = _available()
            if free >= _FREE_FLOOR:
                continue
            print(f"[residency] pressure free~{free / _GB:.1f}GB < floor "
                  f"{_FREE_FLOOR / _GB:.1f}GB - demoting vision to on_demand")
            _unload_vision()
            _persist("on_demand", reason="ram_pressure")
            return


def _start_monitor() -> None:
    global _monitor_thread
    _stop_monitor()
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(
        target=_pressure_loop, daemon=True, name="residency-pressure",
    )
    _monitor_thread.start()


def warm_for_startup() -> dict:
    """App/API launch: pin text only. Do not load vision.

    Always ends in vision=idle so setup UI cannot hang on a partial warm.
    Tries to load the text model even when free RAM is under the cold-load
    floor — refusing forever leaves summarizer/distil with no work path.
    """
    with _lock:
        _stop_monitor()
    before = _available()
    print(f"[residency] startup warm (text only)  free~{before / _GB:.1f}GB")

    _state_path().write_text(
        json.dumps(
            {"status": "warming", "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
            indent=2,
        ),
        encoding="utf-8",
    )

    reason = "startup_text_only"
    err = None
    try:
        try:
            if text_model_loaded(TEXT_MODEL):
                print(f"[residency] text already resident — skip warm  free~{before / _GB:.1f}GB")
                reason = "already_resident"
            elif ensure_text_model(force=True):
                reason = "startup_text_only"
            else:
                reason = "text_warmup_failed"
                err = "warm attempt failed or model not resident after generate"
        except Exception as e:
            print(f"[residency] text warm failed: {e}")
            reason = "text_warmup_failed"
            err = str(e)

        payload = dict(
            reason=reason,
            available_before_mb=_mb(before),
        )
        if err:
            payload["error"] = err
        with _lock:
            return _persist("idle", **payload)
    except Exception as e:
        print(f"[residency] startup warm crashed: {e}")
        with _lock:
            return _persist(
                "idle",
                reason="startup_warm_error",
                error=str(e),
                available_before_mb=_mb(before),
            )


def on_capture_start() -> dict:
    """Keep capture model-free; accessibility and OCR handle screen text."""
    with _lock:
        _stop_monitor()
        return _persist("idle", reason="capture_text_only", vision_warm_skipped=True)


def on_capture_stop() -> dict:
    """Record the idle state; capture never loads a vision model."""
    with _lock:
        _stop_monitor()
        return _persist("idle", reason="capture_stop")



# Seed from disk for gateway imports (capture or API process)
load_residency()


if __name__ == "__main__":
    warm_for_startup()
