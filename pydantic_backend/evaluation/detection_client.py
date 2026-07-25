"""pydantic-ai agent for detecting tender TOC sections via the LiteLLM gateway."""
from __future__ import annotations

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials

_SYSTEM_PROMPT = (
    'You are reviewing the table of contents of a tender/RFP document. '
    'Identify which single TOC heading most likely introduces the "Technical Requirements / '
    'Technical Specifications / Scope of Work" section, and which single TOC heading most '
    'likely introduces the "Price / Commercial / Financial / Pricing Compliance" section. '
    'Use the heading text exactly as it appears in the TOC (drop the leading level marker if '
    'the TOC uses a "level;heading" format). If no suitable section exists, use null.'
)


class _HeadingDetection(BaseModel):
    technical_heading: str | None = None
    price_heading: str | None = None


async def detect_sections(creds: LlmCredentials, toc_text: str) -> tuple[str | None, str | None]:
    """Ask the LLM which TOC heading covers technical requirements and which covers price. Returns (technical, price)."""
    agent = structured_agent(creds, _HeadingDetection, _SYSTEM_PROMPT)
    result = await agent.run(f'TOC:\n{toc_text}')
    return result.output.technical_heading or None, result.output.price_heading or None
