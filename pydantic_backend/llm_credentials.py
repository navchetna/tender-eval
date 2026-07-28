"""
LiteLLM gateway credentials for the two model tiers this app uses: a fast, locally NPU-served
model (extraction/matching/drafting calls) and a quality cloud model (judgment/scoring/comparison
calls). Both go through the same local LiteLLM proxy, differing only in which `model` alias they
request — the proxy's model_list maps each alias to its actual backend.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass
class LlmCredentials:
    """What a single LLM chat-completion call needs: whose key, and where/what model to hit."""

    api_key: str
    base_url: str
    model: str
    verify_tls: bool = True


def fast_llm_credentials(settings: Settings) -> LlmCredentials:
    """For extraction/matching/drafting calls (detect_sections, match_rows, match_headers,
    notify_reviewer) — routed to the NPU-served model."""
    return LlmCredentials(
        api_key=settings.litellm_master_key.get_secret_value(),
        base_url=settings.litellm_base_url,
        model=settings.litellm_fast_model,
        verify_tls=settings.litellm_verify_tls,
    )


def quality_llm_credentials(settings: Settings) -> LlmCredentials:
    """For judgment calls (judge_row, score_section, compare_bids) — routed to the cloud model."""
    return LlmCredentials(
        api_key=settings.litellm_master_key.get_secret_value(),
        base_url=settings.litellm_base_url,
        model=settings.litellm_quality_model,
        verify_tls=settings.litellm_verify_tls,
    )
