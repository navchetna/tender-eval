"""Model download + device selection shared by the in-process LLM and OCR pipelines."""
from __future__ import annotations

import threading
from pathlib import Path

import logfire_api as logfire

from ..config import Settings

# Written after a snapshot download finishes, so a download interrupted halfway (app closed,
# network drop) is resumed on the next start instead of being mistaken for a complete model.
_COMPLETE_MARKER = '.download-complete'

_download_locks: dict[str, threading.Lock] = {}
_download_locks_guard = threading.Lock()


def model_dir(settings: Settings, repo_id: str) -> Path:
    return Path(settings.models_dir) / repo_id.replace('/', '--')


def ensure_model(settings: Settings, repo_id: str) -> Path:
    """Return the local folder of `repo_id`, downloading it from Hugging Face first if needed.
    Blocking — call from a worker thread."""
    target = model_dir(settings, repo_id)
    if (target / _COMPLETE_MARKER).is_file():
        return target

    with _download_locks_guard:
        lock = _download_locks.setdefault(repo_id, threading.Lock())
    with lock:
        if (target / _COMPLETE_MARKER).is_file():
            return target
        from huggingface_hub import snapshot_download

        with logfire.span('local_models.download', repo_id=repo_id, target=str(target)):
            target.mkdir(parents=True, exist_ok=True)
            snapshot_download(repo_id=repo_id, local_dir=str(target))
            (target / _COMPLETE_MARKER).write_text('ok', encoding='utf-8')
    return target


def available_devices() -> list[str]:
    import openvino as ov

    return [name.split('.')[0] for name in ov.Core().available_devices]


def device_candidates(preferred: str) -> list[str]:
    """`preferred` first, then GPU, then CPU — skipping any device this machine doesn't have.
    AUTO/HETERO style strings are passed through untouched for OpenVINO to resolve."""
    preferred = (preferred or 'CPU').upper()
    if ':' in preferred or preferred.startswith('AUTO'):
        return [preferred, 'CPU']
    present = set(available_devices())
    ordered: list[str] = []
    for device in (preferred, 'GPU', 'CPU'):
        if device in present and device not in ordered:
            ordered.append(device)
    return ordered or ['CPU']


def cache_dir(settings: Settings) -> str:
    path = Path(settings.ov_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
