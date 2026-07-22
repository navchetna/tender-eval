"""
Asks an LLM to holistically score each bidder's entire section (technical or price) against
the tender, with individual reasoning plus one comparative narrative across all bidders —
same call-shape as `evaluation/compliance_client.py` (plain httpx, JSON-mode chat completion).

Unlike `compliance_service.judge_row` (per-row compliant/partial/non-compliant), this looks at
the whole normalized view at once, so the model can weigh trade-offs across rows and rank
bidders relative to each other, not just clause-by-clause. Nothing here is persisted — computed
fresh per request, same as the rest of `normalization/`.
"""
from __future__ import annotations

from ..config import Settings
from .groq_json import call_json
from .models import BidScore, NormalizedView, SectionScoreResult

_SYSTEM_PROMPT = (
    'You are a procurement evaluator. You are given a tender\'s requirement rows for one section '
    '(technical or price/commercial), and every bidder\'s matched responses across all of those '
    'rows. Score EACH bidder\'s section holistically from 0-100, weighing completeness, quality, '
    'and compliance across every row together — not just a row-by-row average. Then write one '
    '"comparison" paragraph that explicitly compares the bidders against each other and explains '
    'why one scored higher or lower than another (cite concrete differences in their responses). '
    'Only score bidders explicitly given — never invent one. '
    'Reply with strict JSON only, in this exact shape: '
    '{"scores": [{"bidder": "<name exactly as given>", "score": <integer 0-100>, '
    '"reasoning": "<2-4 sentences on why this bidder got this score>"}], '
    '"comparison": "<paragraph comparing all bidders relative to each other>"} '
    'with exactly one entry in "scores" per bidder given.'
)


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


async def score_section(settings: Settings, view: NormalizedView) -> SectionScoreResult:
    body_text, bidders = flatten_view(view)
    if not bidders:
        return SectionScoreResult(
            project_id=view.project_id, version=view.version, topic=view.topic, scores=[], comparison='No approved bidder responses to score yet.',
        )

    prompt = f'Section: {view.topic.value}\n\n{body_text}'
    parsed = await call_json(settings, _SYSTEM_PROMPT, prompt)

    scores = [
        BidScore(bidder=item['bidder'], score=int(item['score']), reasoning=item.get('reasoning') or '')
        for item in parsed.get('scores', [])
        if item.get('bidder') in bidders
    ]
    return SectionScoreResult(
        project_id=view.project_id, version=view.version, topic=view.topic,
        scores=scores, comparison=parsed.get('comparison') or '',
    )
