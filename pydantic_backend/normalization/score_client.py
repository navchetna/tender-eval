"""
Asks an LLM to holistically score each merchant's entire section (payment or service
compliance) against the circular, with individual reasoning plus one comparative narrative
across all merchants — same pydantic-ai agent call-shape as `evaluation/compliance_client.py`.

Unlike `compliance_service.judge_row` (per-clause compliant/partial/non-compliant), this looks
at the whole normalized view at once, so the model can weigh trade-offs across clauses and rank
merchants relative to each other, not just clause-by-clause. Nothing here is persisted —
computed fresh per request, same as the rest of `normalization/`.

Uses max_tokens=4096 + reasoning_effort='low': reasoning models (e.g. gpt-oss) spend tokens on
hidden reasoning before the JSON body, and a whole-section prompt (multiple merchants, many
clauses) needs enough budget that the reasoning doesn't crowd out the actual answer.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials
from .models import BidScore, NormalizedView, SectionScoreResult


def canonical_merchant(name: str, merchants: list[str]) -> str | None:
    """
    Map a model-returned merchant name back to its canonical label (the file-name stem, e.g.
    'QuickKart-merchant-self-certification'). Models routinely shorten those labels to just the
    business name ('QuickKart'), and a strict equality check then silently drops every score or
    assessment — an empty result that looks exactly like the model having answered nothing.
    Returns None if the name resembles no known merchant (an invented one).
    """
    if name in merchants:
        return name
    lowered = name.strip().lower()
    if not lowered:
        return None
    for merchant in merchants:
        if lowered in merchant.lower() or merchant.lower() in lowered:
            return merchant
    best, best_ratio = None, 0.0
    for merchant in merchants:
        ratio = SequenceMatcher(None, lowered, merchant.lower()).ratio()
        if ratio > best_ratio:
            best, best_ratio = merchant, ratio
    return best if best_ratio >= 0.6 else None

DEFAULT_SYSTEM_PROMPT = (
    'You are an NPCI compliance assessor. You are given the regulator\'s checklist clauses for '
    'one section (payment compliance or service compliance), and every merchant\'s matched '
    'self-certified responses across all of those clauses. Score EACH merchant\'s section '
    'holistically from 0-100 as a compliance score (100 = fully compliant with supporting '
    'evidence; deduct for gaps, missing attestations, unverified self-attested claims, breached '
    'thresholds/TATs, and overdue remediations) — not just a clause-by-clause average. Then '
    'write one "comparison" paragraph that explicitly compares the merchants\' compliance '
    'postures against each other and explains why one scored higher or lower than another '
    '(cite concrete differences in their responses). '
    'Only score merchants explicitly given — never invent one. '
    'Reply with exactly one score per merchant given, using the "bidder" field for the '
    'merchant\'s name.'
)


class _ScoreResponse(BaseModel):
    scores: list[BidScore]
    comparison: str = ''


def flatten_view(view: NormalizedView) -> tuple[str, list[str]]:
    bidders: list[str] = []
    seen: set[str] = set()
    for col in view.bid_columns:
        label = col.split(': ', 1)[0]
        if label not in seen:
            seen.add(label)
            bidders.append(label)

    lines: list[str] = []
    for i, row in enumerate(view.rows, start=1):
        requirement = ' | '.join(f'{k}: {v}' for k, v in row.tender_cells.items() if v)
        lines.append(f'Row {i} — {requirement or "(no requirement text)"}')
        for bidder in bidders:
            fields = [
                f'{col.split(": ", 1)[1]}: {value}'
                for col, value in row.bid_values.items()
                if col.startswith(f'{bidder}: ') and value
            ]
            lines.append(f'  {bidder}: {" | ".join(fields) if fields else "(no response)"}')
    return '\n'.join(lines), bidders


async def score_section(
    creds: LlmCredentials, view: NormalizedView, system_prompt: str | None = None,
) -> SectionScoreResult:
    body_text, bidders = flatten_view(view)
    if not bidders:
        return SectionScoreResult(
            project_id=view.project_id, version=view.version, topic=view.topic, scores=[], comparison='No approved merchant submissions to score yet.',
        )

    prompt = f'Section: {view.topic.value}\n\n{body_text}'
    agent = structured_agent(creds, _ScoreResponse, system_prompt or DEFAULT_SYSTEM_PROMPT, max_tokens=4096, reasoning_effort='low')
    result = await agent.run(prompt)

    scores: list[BidScore] = []
    seen: set[str] = set()
    for s in result.output.scores:
        label = canonical_merchant(s.bidder, bidders)
        if label is None or label in seen:
            continue
        seen.add(label)
        scores.append(s.model_copy(update={'bidder': label}))
    return SectionScoreResult(
        project_id=view.project_id, version=view.version, topic=view.topic,
        scores=scores, comparison=result.output.comparison,
    )
