"""
Shared pydantic-ai agent construction for the local LiteLLM gateway.

Every LLM call in this backend goes through a pydantic_ai.Agent — never raw httpx — so the
whole pipeline shows up as GenAI agent traces in Logfire once `logfire.instrument_pydantic_ai()`
is enabled (see observability.py), not just the one hand-built agent in evaluation/notify_agent.py.
"""
from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import PromptedOutput
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from .llm_credentials import LlmCredentials

OutputT = TypeVar('OutputT', bound=BaseModel)


class LlmConfigError(RuntimeError):
    """A model tier is misconfigured (missing/wrong key) — app.py maps this to a 503."""


def build_model(creds: LlmCredentials) -> Model:
    if creds.provider == 'openvino':
        # Imported lazily: the LiteLLM deployment doesn't install openvino-genai at all.
        from .local_models.llm import in_process_model

        return in_process_model()
    if creds.provider == 'anthropic':
        if not creds.api_key.startswith('sk-ant-'):
            # Fail fast with a fixable message instead of a 401 from api.anthropic.com. The usual
            # cause is a LiteLLM/gateway key pasted here — that belongs in QUALITY_LLM_API_KEY.
            raise LlmConfigError(
                'ANTHROPIC_API_KEY is missing or is not an Anthropic API key (those start with '
                '"sk-ant-"). To use a LiteLLM/enterprise gateway key instead, set '
                'QUALITY_LLM_BASE_URL, QUALITY_LLM_API_KEY and QUALITY_LLM_MODEL in Settings.'
            )
        return AnthropicModel(creds.model, provider=AnthropicProvider(api_key=creds.api_key))
    provider = OpenAIProvider(
        base_url=creds.base_url, api_key=creds.api_key,
        http_client=httpx.AsyncClient(verify=creds.verify_tls),
    )
    return OpenAIChatModel(creds.model, provider=provider)


def structured_agent(
    creds: LlmCredentials,
    output_type: type[OutputT],
    system_prompt: str,
    *,
    retries: int = 2,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> Agent[None, OutputT]:
    """A one-shot, tool-free agent that replies with a validated `output_type` instance.

    Uses PromptedOutput (schema instructions folded into the prompt, JSON reply parsed and
    validated) rather than tool-call-based structured output, matching the plain JSON-mode
    completions this replaces without depending on the gateway model's function-calling support.
    """
    # No fixed temperature: the quality tier (llm_credentials.quality_llm_credentials) routes to
    # an Anthropic model, and Anthropic rejects any temperature other than 1 unless extended
    # thinking is enabled.
    model_settings: dict = {}
    if max_tokens is not None:
        model_settings['max_tokens'] = max_tokens
    if reasoning_effort is not None and creds.provider == 'openai':
        model_settings['openai_reasoning_effort'] = reasoning_effort
    return Agent(
        build_model(creds),
        output_type=PromptedOutput(output_type),
        system_prompt=system_prompt,
        retries=retries,
        model_settings=model_settings,
    )
