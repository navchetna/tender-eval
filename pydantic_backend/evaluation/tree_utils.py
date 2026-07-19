"""
Helpers for locating a TOC heading inside the parser's output_tree.json and pulling out
that section's full text content (including nested subsections).

The exact schema produced by the docling async parser isn't pinned down in this repo, so
the walker below is deliberately lenient: it looks for the common key spellings a
heading/section-tree node is likely to use, and falls back gracefully instead of raising.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from typing import Any

_HEADING_KEYS = ('heading', 'title', 'name', 'section_title')
_TEXT_KEYS = ('text', 'content', 'body')
_CHILD_KEYS = ('children', 'sections', 'nodes', 'subsections')

_MATCH_THRESHOLD = 0.55


def _heading_of(node: dict) -> str | None:
    for key in _HEADING_KEYS:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _own_text(node: dict) -> str:
    parts: list[str] = []
    for key in _TEXT_KEYS:
        value = node.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    # e.g. {"content": "..."} table/text wrapper objects
                    for tkey in _TEXT_KEYS:
                        if isinstance(item.get(tkey), str):
                            parts.append(item[tkey])
    return '\n'.join(p for p in parts if p)


def _children_of(node: dict) -> list[dict]:
    for key in _CHILD_KEYS:
        value = node.get(key)
        if isinstance(value, list):
            return [child for child in value if isinstance(child, dict)]
    return []


def _collect_text(node: dict) -> str:
    """Own text + all descendant text, in document order."""
    parts = [_own_text(node)]
    for child in _children_of(node):
        parts.append(_collect_text(child))
    return '\n'.join(p for p in parts if p)


def _iter_all(node: Any):
    if isinstance(node, dict):
        yield node
        for child in _children_of(node):
            yield from _iter_all(child)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_all(item)


def find_section(tree_json: bytes | str, heading: str) -> tuple[str | None, str | None]:
    """
    Search the tree for the node whose heading best matches `heading` (fuzzy match).

    Returns (matched_heading, section_text) or (None, None) if nothing matched well enough.
    """
    data = json.loads(tree_json) if isinstance(tree_json, (bytes, str)) else tree_json
    best_ratio = 0.0
    best_node: dict | None = None
    best_heading: str | None = None
    for node in _iter_all(data):
        node_heading = _heading_of(node)
        if not node_heading:
            continue
        ratio = SequenceMatcher(None, node_heading.lower(), heading.lower()).ratio()
        if ratio > best_ratio:
            best_ratio, best_node, best_heading = ratio, node, node_heading
    if best_node is None or best_ratio < _MATCH_THRESHOLD:
        return None, None
    return best_heading, _collect_text(best_node)
