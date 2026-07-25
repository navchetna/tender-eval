"""
Judges bidder compliance against one tender requirement row, via a pydantic-ai agent on the
LiteLLM gateway — same call-shape as `detection_client.py` / `normalization/align_client.py`.

This is the one piece of the pipeline that renders a *judgment* (compliant/partial/non-compliant),
rather than just aligning/matching text. Nothing here is persisted — it's computed fresh per
request, consistent with the rest of `normalization/` never persisting its comparison views.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials

_SYSTEM_PROMPT = (
    'You are a procurement compliance reviewer. You are given one requirement row from a '
    'tender/RFP document, and one or more bidders\' responses to that same row. For EACH '
    'bidder given, judge whether their response satisfies the requirement: '
    '"compliant" (fully meets or exceeds it), "partial" (meets it in part, with a gap or '
    'unverified claim), or "non_compliant" (fails to meet it, contradicts it, or is a material '
    'gap). Only judge bidders explicitly given — never invent a bidder. '
    'For each bidder, give a "summary" (under 8 words, e.g. "SIL-4, cert ref A-220") and a '
    '"rationale" (1-2 sentences explaining the judgment, citing the bidder\'s own wording), '
    'with exactly one verdict per bidder given.'
)

_STATUS_TO_TONE = {'compliant': 'ok', 'partial': 'warn', 'non_compliant': 'bad'}
_STATUS_TO_LABEL = {'compliant': 'Compliant', 'partial': 'Partial', 'non_compliant': 'Non-compliant'}


class _Verdict(BaseModel):
    bidder: str
    status: Literal['compliant', 'partial', 'non_compliant']
    summary: str = ''
    rationale: str = ''


class _Verdicts(BaseModel):
    verdicts: list[_Verdict]


async def judge_row(creds: LlmCredentials, requirement: str, bidder_texts: dict[str, str]) -> dict[str, dict]:
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

    agent = structured_agent(creds, _Verdicts, _SYSTEM_PROMPT)
    result = await agent.run(prompt)

    verdicts: dict[str, dict] = {}
    for item in result.output.verdicts:
        if item.bidder not in bidder_texts:
            continue
        verdicts[item.bidder] = {
            's': _STATUS_TO_TONE[item.status],
            't': _STATUS_TO_LABEL[item.status],
            'x': item.summary,
            'full': item.rationale,
        }
    return verdicts
