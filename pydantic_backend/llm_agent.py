"""
Shared pydantic-ai agent construction for the LiteLLM gateway (enterprise agentic toolkit).

Every LLM call in this backend goes through a pydantic_ai.Agent — never raw httpx — so the
whole pipeline shows up as GenAI agent traces in Logfire once `logfire.instrument_pydantic_ai()`
is enabled (see observability.py), not just the one hand-built agent in evaluation/notify_agent.py.
"""
from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider

from .llm_credentials import LlmCredentials

OutputT = TypeVar('OutputT', bound=BaseModel)


def build_model(creds: LlmCredentials) -> OpenAIChatModel:
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
    model_settings: dict = {'temperature': 0}
    if max_tokens is not None:
        model_settings['max_tokens'] = max_tokens
    if reasoning_effort is not None:
        model_settings['openai_reasoning_effort'] = reasoning_effort
    return Agent(
        build_model(creds),
        output_type=PromptedOutput(output_type),
        system_prompt=system_prompt,
        retries=retries,
        model_settings=model_settings,
    )
