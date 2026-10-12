"""
The fast-tier LLM (Qwen3-4B-Instruct, NPU by default) as an in-process OpenVINO GenAI
`LLMPipeline`, exposed to pydantic-ai as a `FunctionModel` so every existing
`structured_agent(...)` call site works unchanged — same PromptedOutput validation, same retries,
same Logfire agent spans — it just never leaves the process.

The pipeline is loaded once, lazily, and shared. OpenVINO pipelines aren't safe to call
concurrently, so generation is serialized behind a lock and run in a worker thread to keep the
event loop free; callers that fan out (asyncio.gather over rows/bids) simply queue up.
"""
from __future__ import annotations

import asyncio
import json
import threading

import logfire_api as logfire
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from ..config import get_settings
from .store import cache_dir, device_candidates, ensure_model


class _FastLLM:
    def __init__(self) -> None:
        self._pipe = None
        self.device: str | None = None
        self._load_lock = threading.Lock()
        self._generate_lock = threading.Lock()
        self._structured_output_ok = True

    def load(self):
        """Download (first run only), compile and return the pipeline. Blocking."""
        if self._pipe is not None:
            return self._pipe
        with self._load_lock:
            if self._pipe is not None:
                return self._pipe
            import openvino_genai as ov_genai

            settings = get_settings()
            path = ensure_model(settings, settings.local_fast_model_repo)
            errors: list[str] = []
            for device in device_candidates(settings.local_fast_model_device):
                config: dict = {'CACHE_DIR': cache_dir(settings)}
                if device == 'NPU':
                    config['MAX_PROMPT_LEN'] = settings.local_fast_model_max_prompt_len
                    config['MIN_RESPONSE_LEN'] = settings.local_fast_model_max_new_tokens
                try:
                    with logfire.span('local_models.llm.load', device=device, model=str(path)):
                        self._pipe = ov_genai.LLMPipeline(str(path), device, **config)
                    self.device = device
                    return self._pipe
                except Exception as exc:  # noqa: BLE001 — try the next device
                    logfire.warn('local_models.llm.load failed', device=device, error=str(exc))
                    errors.append(f'{device}: {exc}')
            raise RuntimeError('Could not load the local LLM on any device: ' + ' | '.join(errors))

    def generate(self, messages: list[dict], json_schema: dict | None, max_new_tokens: int) -> tuple[str, int, int]:
        """Return (text, input_tokens, output_tokens). Blocking."""
        import openvino_genai as ov_genai

        pipe = self.load()
        with self._generate_lock:
            prompt = pipe.get_tokenizer().apply_chat_template(messages, add_generation_prompt=True)
            config = pipe.get_generation_config()
            config.max_new_tokens = max_new_tokens
            config.do_sample = False
            config.apply_chat_template = False  # already applied above, with the system prompt
            if json_schema is not None and self._structured_output_ok:
                # Grammar-constrained decoding: the reply is guaranteed to parse against the
                # schema, so PromptedOutput validation (and its retry round-trips) rarely fires.
                config.structured_output_config = ov_genai.StructuredOutputConfig(json_schema=json.dumps(json_schema))
            try:
                result = pipe.generate([prompt], config)
            except Exception:
                if config.structured_output_config is None:
                    raise
                # Some device/version combinations reject constrained decoding — fall back to
                # plain prompted JSON (still validated + retried by pydantic-ai) from now on.
                logfire.warn('local_models.llm: structured output unsupported here, disabling', device=self.device)
                self._structured_output_ok = False
                config.structured_output_config = None
                result = pipe.generate([prompt], config)
            metrics = result.perf_metrics
            return result.texts[0], metrics.get_num_input_tokens(), metrics.get_num_generated_tokens()


_llm = _FastLLM()


def preload() -> str:
    """Load the fast LLM now (downloading/compiling as needed); returns the device it landed on."""
    _llm.load()
    return _llm.device or ''


def _to_chat(messages: list[ModelMessage], instructions: str | None) -> list[dict]:
    system: list[str] = []
    chat: list[dict] = []
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    system.append(part.content)
                elif isinstance(part, UserPromptPart):
                    content = part.content if isinstance(part.content, str) else '\n'.join(
                        str(item) for item in part.content if isinstance(item, str)
                    )
                    chat.append({'role': 'user', 'content': content})
                elif isinstance(part, RetryPromptPart):
                    chat.append({'role': 'user', 'content': part.model_response()})
        elif isinstance(message, ModelResponse):
            text = ''.join(part.content for part in message.parts if isinstance(part, TextPart))
            if text:
                chat.append({'role': 'assistant', 'content': text})
    if instructions:
        system.append(instructions.strip())
    if system:
        chat.insert(0, {'role': 'system', 'content': '\n\n'.join(system)})
    return chat


async def _run(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    settings = get_settings()
    max_new_tokens = (info.model_settings or {}).get('max_tokens') or settings.local_fast_model_max_new_tokens
    output_object = info.model_request_parameters.output_object
    json_schema = output_object.json_schema if output_object is not None else None
    text, input_tokens, output_tokens = await asyncio.to_thread(
        _llm.generate, _to_chat(messages, info.instructions), json_schema, max_new_tokens,
    )
    return ModelResponse(
        parts=[TextPart(text)],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        model_name=settings.local_fast_model_repo,
        provider_name=f'openvino:{_llm.device or "?"}',
    )


_model: FunctionModel | None = None


def in_process_model() -> FunctionModel:
    global _model
    if _model is None:
        _model = FunctionModel(_run, model_name=f'openvino:{get_settings().local_fast_model_repo}')
    return _model
