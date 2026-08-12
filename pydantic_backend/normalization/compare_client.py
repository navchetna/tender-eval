"""
Asks an LLM for an extended, overall comparison across BOTH technical and price sections
together — one score per bidder plus explicit pros/cons/precautions and an overall
recommendation. This is the "detailed overview" behind the Comparison tab: broader than
`score_client.score_section` (which scores one topic at a time with a short comparison
paragraph), and complementary to `evaluation/compliance_client.judge_row` (per-row verdicts).
Nothing here is persisted — computed fresh per request.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials
from .models import BidAssessment, ComparisonResult, NormalizedView
from .score_client import flatten_view

DEFAULT_SYSTEM_PROMPT = (
    'You are a senior procurement evaluator making a final award recommendation. You are given '
    'a tender\'s technical requirements and/or price/commercial line items, each with every '
    'bidder\'s matched responses. For EACH bidder, give: a "score" (integer 0-100, weighing '
    'technical completeness/quality and price competitiveness together if both are given), '
    '"pros" (list of specific strengths, citing their own responses), "cons" (list of specific '
    'gaps, weaknesses, or missing information), and "precautions" (list of risks or caveats a '
    'buyer should watch for before awarding to this bidder, e.g. unverified claims, ambiguous '
    'wording, higher cost, missing certifications). Then set "recommended_bidder" to the name of '
    'the single best overall bidder (or null if it is a genuine tie or there is not enough data), '
    'and a "recommendation" paragraph explaining the overall award decision and trade-offs. '
    'Only assess bidders explicitly given — never invent one. '
    'Reply with exactly one assessment per bidder given.'
)


class _ComparisonResponse(BaseModel):
    assessments: list[BidAssessment]
    recommended_bidder: str | None = None
    recommendation: str = ''


async def compare_bids(
    creds: LlmCredentials, project_id: str, version: int,
    technical_view: NormalizedView | None, price_view: NormalizedView | None,
    system_prompt: str | None = None,
) -> ComparisonResult:
    sections: list[str] = []
    bidders: list[str] = []
    for label, view in (('TECHNICAL SECTION', technical_view), ('PRICE SECTION', price_view)):
        if view is None:
            continue
        body_text, view_bidders = flatten_view(view)
        sections.append(f'{label}:\n{body_text}')
        for b in view_bidders:
            if b not in bidders:
                bidders.append(b)

    if not bidders:
        return ComparisonResult(
            project_id=project_id, version=version, assessments=[],
            recommended_bidder=None, recommendation='No approved bidder responses to compare yet.',
        )

    prompt = '\n\n'.join(sections)
    agent = structured_agent(creds, _ComparisonResponse, system_prompt or DEFAULT_SYSTEM_PROMPT, max_tokens=4096, reasoning_effort='low')
    result = await agent.run(prompt)

    assessments = [
        BidAssessment(
            bidder=item.bidder, score=item.score,
            pros=[p for p in item.pros if p], cons=[c for c in item.cons if c],
            precautions=[p for p in item.precautions if p],
        )
        for item in result.output.assessments
        if item.bidder in bidders
    ]
    recommended = result.output.recommended_bidder
    return ComparisonResult(
        project_id=project_id, version=version, assessments=assessments,
        recommended_bidder=recommended if recommended in bidders else None,
        recommendation=result.output.recommendation,
    )
