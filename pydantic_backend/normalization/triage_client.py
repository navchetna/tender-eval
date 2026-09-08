"""
Asks an LLM for a risk triage across BOTH payment and service compliance sections together —
one risk assessment per merchant (risk level, compliance score, key gaps, remediation
priorities) plus an audit-priority ranking across all merchants. This is the "who needs audit
attention first" view behind the Risk Triage tab: broader than `score_client.score_section`
(which scores one topic at a time with a short comparison paragraph), and complementary to
`evaluation/compliance_client.judge_row` (per-clause verdicts). Unlike the award-style
comparison it replaces, it deliberately does NOT pick a single winner — a regulator ranks
merchants by risk, it doesn't award to one. Nothing here is persisted — computed fresh per
request.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials
from .models import MerchantAssessment, NormalizedView, RiskTriageResult
from .score_client import canonical_merchant, flatten_view

DEFAULT_SYSTEM_PROMPT = (
    'You are an NPCI supervisory analyst performing risk triage across merchants\' compliance '
    'self-certifications. You are NOT picking a winner — you are ranking merchants by '
    'compliance risk to decide who needs audit attention first. You are given the regulator\'s '
    'payment-compliance and/or service-compliance checklist clauses, each with every '
    'merchant\'s matched self-certified responses. For EACH merchant, give: a "risk_level" '
    '("high" = material payment-compliance failures, missing or expired attestations (e.g. '
    'PCI-DSS AOC), or settlement/security gaps; "medium" = partial compliance, unverified '
    'self-attested claims, or service-side breaches; "low" = substantially compliant with '
    'supporting evidence), a "score" (integer 0-100 compliance score across whatever sections '
    'were given), "key_gaps" (list of specific compliance gaps, citing the merchant\'s own '
    'responses and clause references), and "remediation_priorities" (ordered list of concrete '
    'remediation actions, most urgent first). Then set "audit_priority_order" to a list '
    'containing every given merchant exactly once, ordered from most audit-urgent to least '
    '(higher risk first; break ties by lower compliance score first), and write a "summary" '
    'paragraph explaining the triage — who needs audit attention first and why. '
    'Only assess merchants explicitly given — never invent one. '
    'Reply with exactly one assessment per merchant given.'
)

_RISK_RANK = {'high': 0, 'medium': 1, 'low': 2}


class _TriageAssessment(BaseModel):
    merchant: str
    risk_level: Literal['high', 'medium', 'low']
    score: int
    key_gaps: list[str] = []
    remediation_priorities: list[str] = []


class _TriageResponse(BaseModel):
    assessments: list[_TriageAssessment]
    audit_priority_order: list[str] = []
    summary: str = ''


async def triage_merchants(
    creds: LlmCredentials, project_id: str, version: int,
    payment_view: NormalizedView | None, service_view: NormalizedView | None,
    system_prompt: str | None = None,
) -> RiskTriageResult:
    sections: list[str] = []
    merchants: list[str] = []
    for label, view in (('PAYMENT COMPLIANCE SECTION', payment_view), ('SERVICE COMPLIANCE SECTION', service_view)):
        if view is None:
            continue
        body_text, view_merchants = flatten_view(view)
        sections.append(f'{label}:\n{body_text}')
        for m in view_merchants:
            if m not in merchants:
                merchants.append(m)

    if not merchants:
        return RiskTriageResult(
            project_id=project_id, version=version, assessments=[],
            audit_priority_order=[], summary='No approved merchant submissions to triage yet.',
        )

    merchant_list = '\n'.join(f'- {m}' for m in merchants)
    prompt = f'MERCHANTS (assess each one, using these exact names):\n{merchant_list}\n\n' + '\n\n'.join(sections)
    agent = structured_agent(creds, _TriageResponse, system_prompt or DEFAULT_SYSTEM_PROMPT, max_tokens=4096, reasoning_effort='low')
    result = await agent.run(prompt)

    # Names come back canonicalized: models shorten the file-stem labels to the bare business
    # name, and dropping those on strict equality would empty the whole triage.
    assessments: list[MerchantAssessment] = []
    seen: set[str] = set()
    for item in result.output.assessments:
        label = canonical_merchant(item.merchant, merchants)
        if label is None or label in seen:
            continue
        seen.add(label)
        assessments.append(
            MerchantAssessment(
                merchant=label, risk_level=item.risk_level, score=item.score,
                key_gaps=[g for g in item.key_gaps if g],
                remediation_priorities=[r for r in item.remediation_priorities if r],
            )
        )

    # The ranking must always be total over the assessed merchants: drop names the model
    # invented, then append any merchant it omitted, ordered by (risk level, ascending score).
    assessed = {a.merchant: a for a in assessments}
    ordering: list[str] = []
    for name in result.output.audit_priority_order:
        label = canonical_merchant(name, merchants)
        if label is not None and label in assessed and label not in ordering:
            ordering.append(label)
    missing = [a for a in assessments if a.merchant not in ordering]
    missing.sort(key=lambda a: (_RISK_RANK[a.risk_level], a.score))
    ordering.extend(a.merchant for a in missing)

    return RiskTriageResult(
        project_id=project_id, version=version, assessments=assessments,
        audit_priority_order=ordering, summary=result.output.summary,
    )
