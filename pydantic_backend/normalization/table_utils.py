"""
Parses a section's raw extracted text (markdown tables, or plain prose) into row-level
items for the normalization view. Nothing here is persisted \u2014 it's re-parsed on every
request from whatever is already stored in circular_evaluations/submission_evaluations.
"""
from __future__ import annotations

import html
import re

_SEPARATOR_RE = re.compile(r'^\|?[\s:|-]+\|?$')


def _group_heading(line: str) -> str | None:
    """The group title if `line` is a markdown '#' heading or a whole-line **bold** label —
    the way section documents introduce each of their tables ("## Level 2:- Home screen
    checklist", "**Reports Availability:**")."""
    stripped = line.strip()
    if stripped.startswith('#'):
        text = stripped.lstrip('#').strip()
        return html.unescape(text) if text else None
    if stripped.startswith('**') and stripped.endswith('**') and len(stripped) > 4:
        return html.unescape(stripped.strip('*').strip())
    return None


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
    Parse `content` into row-level items:
    [{"text": "<human-readable row>", "cells": {...}, "group": "<nearest preceding heading>"}, ...].

    Contiguous blocks of lines starting with `|` are treated as markdown tables; each table's
    rows carry the nearest preceding heading/bold-label line as their "group", so a section
    made of many small tables (a multi-level checklist) keeps its structure for display. If no
    table is found at all, falls back to splitting on blank lines so prose-only sections still
    produce comparable "rows" instead of one giant blob.
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines()
    rows: list[dict] = []
    block: list[str] = []
    found_table = False
    current_group: str | None = None

    def _flush():
        nonlocal block
        if block:
            for row in _parse_table_block(block):
                row['group'] = current_group
                rows.append(row)
            block = []

    for line in lines:
        if line.strip().startswith('|'):
            found_table = True
            block.append(line)
        else:
            _flush()
            heading = _group_heading(line)
            if heading is not None:
                current_group = heading
    _flush()

    if found_table:
        return rows

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    return [{'text': p, 'cells': {'text': p}, 'group': None} for p in paragraphs]
