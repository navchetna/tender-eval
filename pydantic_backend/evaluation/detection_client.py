"""pydantic-ai agent for detecting compliance TOC sections via the LiteLLM gateway."""
from __future__ import annotations

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials

_SYSTEM_PROMPT = (
    'You are reviewing the table of contents of an NPCI merchant-compliance document — either '
    'a regulatory compliance circular/guidelines, or a merchant\'s compliance self-certification '
    'submission. Identify which single TOC heading most likely introduces the "Payment '
    'Compliance" section (settlement of transactions and reports, transaction security and '
    'authorization, reconciliation, tokenization, PCI-DSS attestations), and which single TOC '
    'heading most likely introduces the "Service Compliance" section (customer complaints / '
    'grievance redressal, customer registration, app functionality checklists, customer '
    'disclosures, refunds and turnaround times). Prefer a heading whose section contains '
    'concrete checklist tables or itemised obligations over a general introduction. '
    'Use the heading text exactly as it appears in the TOC (drop the leading level marker if '
    'the TOC uses a "level;heading" format). If no suitable section exists, use null.'
)


class _HeadingDetection(BaseModel):
    payment_heading: str | None = None
    service_heading: str | None = None


async def detect_sections(creds: LlmCredentials, toc_text: str) -> tuple[str | None, str | None]:
    """Ask the LLM which TOC heading covers payment compliance and which covers service compliance. Returns (payment, service)."""
    agent = structured_agent(creds, _HeadingDetection, _SYSTEM_PROMPT)
    result = await agent.run(f'TOC:\n{toc_text}')
    return result.output.payment_heading or None, result.output.service_heading or None
