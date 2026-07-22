"""
Aligns one bid's rows/columns against the tender's rows/columns via Groq calls.

This is a semantic match (bidders phrase things differently than the tender), not string
matching. The LLM decides *which* bid row corresponds to each tender row, and *which* bid
column header means the same real-world field as a tender column header (short/ambiguous
headers like "Unit" need real understanding, not character-overlap heuristics, to be mapped
onto the right tender column, e.g. "Unit of Measure" rather than "Unit Cost"). It does not
extract or judge values itself \u2014 that's plain lookup once the mapping is known.
"""
from __future__ import annotations

import json

import httpx

from ..config import Settings

_ROW_SYSTEM_PROMPT = (
    'You are aligning a bidder\'s response rows against a tender\'s requirement/line-item rows '
    'from the same section of a tender/RFP document. For each tender row (by index), find the '
    'single bid row that best corresponds to the same requirement/line item (bidders often '
    'restate the requirement near-verbatim before giving their compliance/response/price for '
    'it). If no bid row plausibly corresponds to a tender row, use null. '
    'Reply with strict JSON only, in this exact shape: '
    '{"matches": [{"tender_index": <int>, "bid_index": <int or null>}, ...]} '
    'with exactly one entry per tender row index.'
)

_HEADER_SYSTEM_PROMPT = (
    'You are mapping a bidder\'s table column headers onto a tender\'s table column headers '
    'from the same section of a tender/RFP document, so matching fields can be compared. For '
    'each bid column header, decide which single tender column header (if any) refers to the '
    'same real-world field. Use your understanding of tender/procurement terminology, not just '
    'text similarity \u2014 for example "Qty" means the same as "Total Quantity"; a short header '
    'like "Unit" that holds values such as "each"/"lump-sum"/"per year" means the same as "Unit '
    'of Measure", NOT "Unit Cost"; "Rate" or "Unit Cost (Ex. Tax)" means "Unit Cost". If a bid '
    'header does not correspond to any given tender column (e.g. "Compliance Status" when the '
    'tender has no such column), use null. '
    'Reply with strict JSON only, in this exact shape: '
    '{"mapping": [{"bid_header": "<string>", "tender_header": "<string or null>"}, ...]} '
    'with exactly one entry per bid column header given.'
)


async def _post_json(settings: Settings, system_prompt: str, user_prompt: str) -> dict:
    async with httpx.AsyncClient(base_url=settings.groq_base_url, timeout=90.0) as client:
        response = await client.post(
            '/chat/completions',
            headers={'Authorization': f'Bearer {settings.groq_api_key.get_secret_value()}'},
            json={
                'model': settings.groq_model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0,
                'response_format': {'type': 'json_object'},
            },
        )
        response.raise_for_status()
        body = response.json()
        content = body['choices'][0]['message']['content']
        return json.loads(content)


async def match_rows(settings: Settings, tender_rows: list[str], bid_rows: list[str]) -> list[int | None]:
    """Return a list the same length as `tender_rows`: each entry is the matched bid row index, or None."""
    if not tender_rows or not bid_rows:
        return [None] * len(tender_rows)

    tender_listing = '\n'.join(f'{i}: {text}' for i, text in enumerate(tender_rows))
    bid_listing = '\n'.join(f'{i}: {text}' for i, text in enumerate(bid_rows))
    prompt = f'Tender rows:\n{tender_listing}\n\nBid rows:\n{bid_listing}'

    parsed = await _post_json(settings, _ROW_SYSTEM_PROMPT, prompt)

    indices: list[int | None] = [None] * len(tender_rows)
    for match in parsed.get('matches', []):
        tender_index = match.get('tender_index')
        bid_index = match.get('bid_index')
        if isinstance(tender_index, int) and 0 <= tender_index < len(indices):
            indices[tender_index] = bid_index if isinstance(bid_index, int) and 0 <= bid_index < len(bid_rows) else None
    return indices


async def match_headers(settings: Settings, tender_columns: list[str], bid_columns: list[str]) -> dict[str, str | None]:
    """Return {bid_header: matched_tender_header_or_None} for one bid's full set of column headers."""
    if not tender_columns or not bid_columns:
        return {header: None for header in bid_columns}

    tender_listing = '\n'.join(tender_columns)
    bid_listing = '\n'.join(bid_columns)
    prompt = f'Tender column headers:\n{tender_listing}\n\nBid column headers:\n{bid_listing}'

    parsed = await _post_json(settings, _HEADER_SYSTEM_PROMPT, prompt)

    mapping: dict[str, str | None] = {header: None for header in bid_columns}
    for item in parsed.get('mapping', []):
        bid_header = item.get('bid_header')
        tender_header = item.get('tender_header')
        if bid_header in mapping:
            mapping[bid_header] = tender_header if tender_header in tender_columns else None
    return mapping
