"""
Aligns one bid's rows/columns against the tender's rows/columns via pydantic-ai agents on the
LiteLLM gateway.

This is a semantic match (bidders phrase things differently than the tender), not string
matching. The LLM decides *which* bid row corresponds to each tender row, and *which* bid
column header means the same real-world field as a tender column header (short/ambiguous
headers like "Unit" need real understanding, not character-overlap heuristics, to be mapped
onto the right tender column, e.g. "Unit of Measure" rather than "Unit Cost"). It does not
extract or judge values itself — that's plain lookup once the mapping is known.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials

_ROW_SYSTEM_PROMPT = (
    'You are aligning a bidder\'s response rows against a tender\'s requirement/line-item rows '
    'from the same section of a tender/RFP document. For each tender row (by index), find the '
    'single bid row that best corresponds to the same requirement/line item (bidders often '
    'restate the requirement near-verbatim before giving their compliance/response/price for '
    'it). If no bid row plausibly corresponds to a tender row, use null. '
    'Reply with exactly one entry per tender row index.'
)

_HEADER_SYSTEM_PROMPT = (
    'You are mapping a bidder\'s table column headers onto a tender\'s table column headers '
    'from the same section of a tender/RFP document, so matching fields can be compared. For '
    'each bid column header, decide which single tender column header (if any) refers to the '
    'same real-world field. Use your understanding of tender/procurement terminology, not just '
    'text similarity — for example "Qty" means the same as "Total Quantity"; a short header '
    'like "Unit" that holds values such as "each"/"lump-sum"/"per year" means the same as "Unit '
    'of Measure", NOT "Unit Cost"; "Rate" or "Unit Cost (Ex. Tax)" means "Unit Cost". If a bid '
    'header does not correspond to any given tender column (e.g. "Compliance Status" when the '
    'tender has no such column), use null. '
    'Reply with exactly one entry per bid column header given.'
)


class _RowMatch(BaseModel):
    tender_index: int
    bid_index: int | None = None


class _RowMatches(BaseModel):
    matches: list[_RowMatch]


class _HeaderMap(BaseModel):
    bid_header: str
    tender_header: str | None = None


class _HeaderMappings(BaseModel):
    mapping: list[_HeaderMap]


async def match_rows(creds: LlmCredentials, tender_rows: list[str], bid_rows: list[str]) -> list[int | None]:
    """Return a list the same length as `tender_rows`: each entry is the matched bid row index, or None."""
    if not tender_rows or not bid_rows:
        return [None] * len(tender_rows)

    tender_listing = '\n'.join(f'{i}: {text}' for i, text in enumerate(tender_rows))
    bid_listing = '\n'.join(f'{i}: {text}' for i, text in enumerate(bid_rows))
    prompt = f'Tender rows:\n{tender_listing}\n\nBid rows:\n{bid_listing}'

    agent = structured_agent(creds, _RowMatches, _ROW_SYSTEM_PROMPT)
    result = await agent.run(prompt)

    indices: list[int | None] = [None] * len(tender_rows)
    for match in result.output.matches:
        if 0 <= match.tender_index < len(indices):
            bid_index = match.bid_index
            indices[match.tender_index] = bid_index if bid_index is not None and 0 <= bid_index < len(bid_rows) else None
    return indices


async def match_headers(creds: LlmCredentials, tender_columns: list[str], bid_columns: list[str]) -> dict[str, str | None]:
    """Return {bid_header: matched_tender_header_or_None} for one bid's full set of column headers."""
    if not tender_columns or not bid_columns:
        return {header: None for header in bid_columns}

    tender_listing = '\n'.join(tender_columns)
    bid_listing = '\n'.join(bid_columns)
    prompt = f'Tender column headers:\n{tender_listing}\n\nBid column headers:\n{bid_listing}'

    agent = structured_agent(creds, _HeaderMappings, _HEADER_SYSTEM_PROMPT)
    result = await agent.run(prompt)

    mapping: dict[str, str | None] = {header: None for header in bid_columns}
    for item in result.output.mapping:
        if item.bid_header in mapping:
            mapping[item.bid_header] = item.tender_header if item.tender_header in tender_columns else None
    return mapping
