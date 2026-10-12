"""
Page OCR (LightOnOCR-3, Arc GPU by default) as an in-process OpenVINO GenAI `VLMPipeline` —
the replacement for llama.cpp's `llama-server` + LightOnOCR-2 GGUF.

LightOnOCR-3-0.8B is built on the Qwen3.5 vision-language architecture, which OpenVINO GenAI
supports natively (LightOnOCR-2's Pixtral+Qwen3 architecture is not), and keeps LightOnOCR-2's
calling convention: an image with an empty prompt returns the whole page as Markdown.
Pages should be rendered with a longest edge of RENDER_LONGEST_EDGE px — the model card's
recommendation; a 1540 px render wasn't faster in testing and transcribed less faithfully.
"""
from __future__ import annotations

import threading

import logfire_api as logfire
import numpy as np

from ..config import get_settings
from .store import cache_dir, device_candidates, ensure_model

RENDER_LONGEST_EDGE = 2048


class _PageOCR:
    def __init__(self) -> None:
        self._pipe = None
        self.device: str | None = None
        self._load_lock = threading.Lock()
        self._generate_lock = threading.Lock()

    def load(self):
        if self._pipe is not None:
            return self._pipe
        with self._load_lock:
            if self._pipe is not None:
                return self._pipe
            import openvino_genai as ov_genai

            settings = get_settings()
            path = ensure_model(settings, settings.local_ocr_model_repo)
            errors: list[str] = []
            for device in device_candidates(settings.local_ocr_model_device):
                try:
                    with logfire.span('local_models.ocr.load', device=device, model=str(path)):
                        self._pipe = ov_genai.VLMPipeline(str(path), device, CACHE_DIR=cache_dir(settings))
                    self.device = device
                    return self._pipe
                except Exception as exc:  # noqa: BLE001 — try the next device
                    logfire.warn('local_models.ocr.load failed', device=device, error=str(exc))
                    errors.append(f'{device}: {exc}')
            raise RuntimeError('Could not load the local OCR model on any device: ' + ' | '.join(errors))

    def page_to_markdown(self, image) -> str:
        """OCR one rendered page (PIL image) into Markdown. Blocking."""
        import openvino as ov
        import openvino_genai as ov_genai

        pipe = self.load()
        rgb = np.asarray(image.convert('RGB'), dtype=np.uint8)
        config = ov_genai.GenerationConfig()
        config.max_new_tokens = get_settings().local_ocr_max_new_tokens
        # Greedy. A repetition penalty measurably hurt transcription (dropped/reworded header
        # lines) in testing; runaway loops on dense tables are bounded by max_new_tokens instead.
        config.do_sample = False
        with self._generate_lock:
            result = pipe.generate('', images=[ov.Tensor(rgb[np.newaxis, ...])], generation_config=config)
        return result.texts[0]


_ocr = _PageOCR()


def preload() -> str:
    _ocr.load()
    return _ocr.device or ''


def page_to_markdown(image) -> str:
    return _ocr.page_to_markdown(image)
