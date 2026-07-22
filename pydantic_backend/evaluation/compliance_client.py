"""
Judges bidder compliance against one tender requirement row, via Groq — same call-shape as
`groq_client.py` / `normalization/align_client.py` (plain httpx, JSON-mode chat completion).

This is the one piece of the pipeline that renders a *judgment* (compliant/partial/non-compliant),
rather than just aligning/matching text. Nothing here is persisted — it's computed fresh per
request, consistent with the rest of `normalization/` never persisting its comparison views.
"""
from __future__ import annotations

import json

import httpx

from ..config import Settings

_SYSTEM_PROMPT = (
    'You are a procurement compliance reviewer. You are given one requirement row from a '
    'tender/RFP document, and one or more bidders\' responses to that same row. For EACH '
    'bidder given, judge whether their response satisfies the requirement: '
    '"compliant" (fully meets or exceeds it), "partial" (meets it in part, with a gap or '
    'unverified claim), or "non_compliant" (fails to meet it, contradicts it, or is a material '
    'gap). Only judge bidders explicitly given — never invent a bidder. '
    'For each bidder, give a "summary" (under 8 words, e.g. "SIL-4, cert ref A-220") and a '
    '"rationale" (1-2 sentences explaining the judgment, citing the bidder\'s own wording). '
    'Reply with strict JSON only, in this exact shape: '
    '{"verdicts": [{"bidder": "<name exactly as given>", '
    '"status": "compliant"|"partial"|"non_compliant", "summary": "<string>", "rationale": "<string>"}]} '
    'with exactly one entry per bidder given.'
)

_STATUS_TO_TONE = {'compliant': 'ok', 'partial': 'warn', 'non_compliant': 'bad'}
_STATUS_TO_LABEL = {'compliant': 'Compliant', 'partial': 'Partial', 'non_compliant': 'Non-compliant'}


async def judge_row(settings: Settings, requirement: str, bidder_texts: dict[str, str]) -> dict[str, dict]:
    """
    `bidder_texts` maps bid_label -> that bidder's flattened response text for this row.
    Returns {bid_label: {"s": tone, "t": label, "x": summary, "full": rationale}}, one entry
    per bidder given (bidders the model fails to return a verdict for are simply absent from
    the result — callers should fall back to a "no verdict" cell for those).
    """
    if not bidder_texts:
        return {}

    bidder_listing = '\n'.join(f'{label}: {text}' for label, text in bidder_texts.items())
    prompt = f'Requirement:\n{requirement}\n\nBidder responses:\n{bidder_listing}'

    async with httpx.AsyncClient(base_url=settings.groq_base_url, timeout=60.0) as client:
        response = await client.post(
            '/chat/completions',
            headers={'Authorization': f'Bearer {settings.groq_api_key.get_secret_value()}'},
            json={
                'model': settings.groq_model,
                'messages': [
                    {'role': 'system', 'content': _SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0,
                'response_format': {'type': 'json_object'},
            },
        )
        response.raise_for_status()
        body = response.json()
        content = body['choices'][0]['message']['content']
        parsed = json.loads(content)

    verdicts: dict[str, dict] = {}
    for item in parsed.get('verdicts', []):
        bidder = item.get('bidder')
        status = item.get('status')
        if bidder not in bidder_texts or status not in _STATUS_TO_TONE:
            continue
        verdicts[bidder] = {
            's': _STATUS_TO_TONE[status],
            't': _STATUS_TO_LABEL[status],
            'x': item.get('summary') or '',
            'full': item.get('rationale') or '',
        }
    return verdicts
