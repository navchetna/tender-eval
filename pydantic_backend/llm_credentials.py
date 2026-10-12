"""
Credentials for the two model tiers this app uses: a fast, locally NPU-served model
(extraction/matching/drafting calls) and a quality cloud model (judgment/scoring/comparison
calls).

With `model_runtime='litellm'` both go through the same local LiteLLM proxy, differing only in
which `model` alias they request — the proxy's model_list maps each alias to its actual backend.
With `model_runtime='inprocess'` the fast tier is an OpenVINO GenAI pipeline loaded into this
process and the quality tier calls Anthropic directly — see llm_agent.build_model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Settings


@dataclass
class LlmCredentials:
    """What a single LLM chat-completion call needs: whose key, and where/what model to hit."""

    api_key: str
    base_url: str
    model: str
    verify_tls: bool = True
    provider: Literal['openai', 'openvino', 'anthropic'] = 'openai'


def fast_llm_credentials(settings: Settings) -> LlmCredentials:
    """For extraction/matching/drafting calls (detect_sections, match_rows, match_headers,
    notify_reviewer) — routed to the NPU-served model."""
    if settings.model_runtime == 'inprocess':
        return LlmCredentials(
            api_key='', base_url='', model=settings.local_fast_model_repo, provider='openvino',
        )
    return LlmCredentials(
        api_key=settings.litellm_master_key.get_secret_value(),
        base_url=settings.litellm_base_url,
        model=settings.litellm_fast_model,
        verify_tls=settings.litellm_verify_tls,
    )


def quality_llm_credentials(settings: Settings) -> LlmCredentials:
    """For judgment calls (judge_row, score_section, compare_bids) — routed to the cloud model."""
    if settings.model_runtime == 'inprocess' and settings.quality_llm_base_url:
        return LlmCredentials(
            api_key=settings.quality_llm_api_key.get_secret_value(),
            base_url=settings.quality_llm_base_url,
            model=settings.quality_llm_model,
            verify_tls=settings.quality_llm_verify_tls,
        )
    if settings.model_runtime == 'inprocess':
        return LlmCredentials(
            api_key=settings.anthropic_api_key.get_secret_value(),
            base_url=settings.anthropic_base_url,
            model=settings.anthropic_quality_model,
            provider='anthropic',
        )
    return LlmCredentials(
        api_key=settings.litellm_master_key.get_secret_value(),
        base_url=settings.litellm_base_url,
        model=settings.litellm_quality_model,
        verify_tls=settings.litellm_verify_tls,
    )
