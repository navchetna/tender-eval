"""
Judges merchant compliance against one circular requirement clause, via a pydantic-ai agent on
the LiteLLM gateway — same call-shape as `detection_client.py` / `normalization/align_client.py`.

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
    'You are an NPCI compliance auditor. You are given one requirement clause from a merchant '
    'compliance checklist circular, and one or more merchants\' self-certified responses to '
    'that same clause. For EACH merchant given, judge whether their self-certification '
    'satisfies the clause: "compliant" (fully meets it, with supporting evidence or attestation '
    'reference), "partial" (meets it in part, or an unverified self-attested claim without '
    'evidence), or "non_compliant" (fails to meet it, contradicts it, breaches the stated '
    'threshold/TAT, or is a material gap). Only judge merchants explicitly given — never '
    'invent a merchant. For each merchant, give a "summary" (under 8 words, e.g. "PCI-DSS AOC '
    'on file, T+1 settlement") and a "rationale" (1-2 sentences explaining the judgment, '
    'citing the merchant\'s own wording), with exactly one verdict per merchant given.'
)

_STATUS_TO_TONE = {'compliant': 'ok', 'partial': 'warn', 'non_compliant': 'bad'}
_STATUS_TO_LABEL = {'compliant': 'Compliant', 'partial': 'Partial', 'non_compliant': 'Non-compliant'}


class _Verdict(BaseModel):
    merchant: str
    status: Literal['compliant', 'partial', 'non_compliant']
    summary: str = ''
    rationale: str = ''


class _Verdicts(BaseModel):
    verdicts: list[_Verdict]


async def judge_row(creds: LlmCredentials, requirement: str, merchant_texts: dict[str, str]) -> dict[str, dict]:
    """
    `merchant_texts` maps merchant label -> that merchant's flattened response text for this
    clause. Returns {label: {"s": tone, "t": label, "x": summary, "full": rationale}}, one
    entry per merchant given (merchants the model fails to return a verdict for are simply
    absent from the result — callers should fall back to a "no verdict" cell for those).
    """
    if not merchant_texts:
        return {}

    merchant_listing = '\n'.join(f'{label}: {text}' for label, text in merchant_texts.items())
    prompt = f'Requirement clause:\n{requirement}\n\nMerchant self-certified responses:\n{merchant_listing}'

    agent = structured_agent(creds, _Verdicts, _SYSTEM_PROMPT)
    result = await agent.run(prompt)

    verdicts: dict[str, dict] = {}
    for item in result.output.verdicts:
        if item.merchant not in merchant_texts:
            continue
        verdicts[item.merchant] = {
            's': _STATUS_TO_TONE[item.status],
            't': _STATUS_TO_LABEL[item.status],
            'x': item.summary,
            'full': item.rationale,
        }
    return verdicts
