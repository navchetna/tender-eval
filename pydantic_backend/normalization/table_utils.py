"""
Parses a section's raw extracted text (markdown tables, or plain prose) into row-level
items for the normalization view. Nothing here is persisted \u2014 it's re-parsed on every
request from whatever is already stored in tender_evaluations/bid_evaluations.
"""
from __future__ import annotations

import re

_SEPARATOR_RE = re.compile(r'^\|?[\s:|-]+\|?$')


def _split_row(line: str) -> list[str]:
    cells = line.strip().split('|')
    if cells and cells[0].strip() == '':
        cells = cells[1:]
    if cells and cells[-1].strip() == '':
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _is_footer_row(row: dict) -> bool:
    """
    Detect degenerate summary/footer rows (e.g. a "Total" row where a merged cell got
    rendered into every column with the same literal text). These aren't real line items
    and would otherwise fool "is this column ever filled in" checks downstream.
    """
    values = [v for v in row.values() if v]
    return len(values) >= 2 and len(set(values)) == 1


def _parse_table_block(lines: list[str]) -> list[dict]:
    if not lines:
        return []
    headers = _split_row(lines[0])
    data_lines = lines[1:]
    if data_lines and _SEPARATOR_RE.match(data_lines[0]):
        data_lines = data_lines[1:]

    rows: list[dict] = []
    for line in data_lines:
        cells = _split_row(line)
        row = {headers[i] if i < len(headers) else f'col_{i}': (cells[i] if i < len(cells) else '') for i in range(max(len(headers), len(cells)))}
        if _is_footer_row(row):
            continue
        text = ' | '.join(f'{k}: {v}' for k, v in row.items() if v)
        if text:
            rows.append({'text': text, 'cells': row})
    return rows


def parse_rows(content: str) -> list[dict]:
    """
    Parse `content` into row-level items: [{"text": "<human-readable row>", "cells": {...}}, ...].

    Contiguous blocks of lines starting with `|` are treated as markdown tables. If no table
    is found at all, falls back to splitting on blank lines so prose-only sections still
    produce comparable "rows" instead of one giant blob.
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines()
    rows: list[dict] = []
    block: list[str] = []
    found_table = False

    def _flush():
        nonlocal block
        if block:
            rows.extend(_parse_table_block(block))
            block = []

    for line in lines:
        if line.strip().startswith('|'):
            found_table = True
            block.append(line)
        else:
            _flush()
    _flush()

    if found_table:
        return rows

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    return [{'text': p, 'cells': {'text': p}} for p in paragraphs]
