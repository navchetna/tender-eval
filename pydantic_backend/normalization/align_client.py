"""
Aligns one merchant submission's rows/columns against the circular's rows/columns via
pydantic-ai agents on the LiteLLM gateway.

This is a semantic match (merchants phrase things differently than the regulator's circular),
not string matching. The LLM decides *which* submission row corresponds to each circular
clause, and *which* submission column header means the same real-world field as a circular
column header (short/ambiguous headers like "TAT" need real understanding, not
character-overlap heuristics, to be mapped onto the right circular column). It does not
extract or judge values itself — that's plain lookup once the mapping is known.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials

_ROW_SYSTEM_PROMPT = (
    'You are aligning a merchant\'s compliance self-certification rows against a regulator\'s '
    'checklist clauses from the same section of an NPCI compliance circular. For each circular '
    'clause (by index), find the single submission row that best corresponds to the same '
    'clause/obligation (merchants often restate the clause near-verbatim before giving their '
    'compliance status and evidence for it). If no submission row plausibly corresponds to a '
    'circular clause, use null. '
    'Reply with exactly one entry per circular clause index.'
)

_HEADER_SYSTEM_PROMPT = (
    'You are mapping a merchant submission\'s table column headers onto a compliance '
    'circular\'s table column headers from the same section, so matching fields can be '
    'compared. For each submission column header, decide which single circular column header '
    '(if any) refers to the same real-world field. Use your understanding of payments/'
    'compliance terminology, not just text similarity — for example "Status" means the same as '
    '"Compliance Status"; a short header like "TAT" that holds values such as "24h"/"T+1"/'
    '"T+5 days" means the same as "Turnaround Time", NOT "Transaction Type"; "Evidence Ref" or '
    '"Attestation" means "Evidence / Attestation Reference". If a submission header does not '
    'correspond to any given circular column (e.g. "Merchant Remarks" when the circular has no '
    'such column), use null. '
    'Reply with exactly one entry per submission column header given.'
)


class _RowMatch(BaseModel):
    circular_index: int
    submission_index: int | None = None


class _RowMatches(BaseModel):
    matches: list[_RowMatch]


class _HeaderMap(BaseModel):
    submission_header: str
    circular_header: str | None = None


class _HeaderMappings(BaseModel):
    mapping: list[_HeaderMap]


async def match_rows(creds: LlmCredentials, tender_rows: list[str], bid_rows: list[str]) -> list[int | None]:
    """Return a list the same length as `tender_rows` (circular clauses): each entry is the
    matched submission row index, or None."""
    if not tender_rows or not bid_rows:
        return [None] * len(tender_rows)

    tender_listing = '\n'.join(f'{i}: {text}' for i, text in enumerate(tender_rows))
    bid_listing = '\n'.join(f'{i}: {text}' for i, text in enumerate(bid_rows))
    prompt = f'Circular clauses:\n{tender_listing}\n\nSubmission rows:\n{bid_listing}'

    agent = structured_agent(creds, _RowMatches, _ROW_SYSTEM_PROMPT)
    result = await agent.run(prompt)

    indices: list[int | None] = [None] * len(tender_rows)
    for match in result.output.matches:
        if 0 <= match.circular_index < len(indices):
            bid_index = match.submission_index
            indices[match.circular_index] = bid_index if bid_index is not None and 0 <= bid_index < len(bid_rows) else None
    return indices


async def match_headers(creds: LlmCredentials, tender_columns: list[str], bid_columns: list[str]) -> dict[str, str | None]:
    """Return {submission_header: matched_circular_header_or_None} for one submission's full set of column headers."""
    if not tender_columns or not bid_columns:
        return {header: None for header in bid_columns}

    tender_listing = '\n'.join(tender_columns)
    bid_listing = '\n'.join(bid_columns)
    prompt = f'Circular column headers:\n{tender_listing}\n\nSubmission column headers:\n{bid_listing}'

    agent = structured_agent(creds, _HeaderMappings, _HEADER_SYSTEM_PROMPT)
    result = await agent.run(prompt)

    mapping: dict[str, str | None] = {header: None for header in bid_columns}
    for item in result.output.mapping:
        if item.submission_header in mapping:
            mapping[item.submission_header] = item.circular_header if item.circular_header in tender_columns else None
    return mapping
