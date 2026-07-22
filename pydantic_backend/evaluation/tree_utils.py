"""
Locate a TOC heading inside the parser's output_tree.json and pull out that section's
full text content (including nested subsections).

Real schema (confirmed from a live parse):
  {"root": {"content": [...], "children": [ {"<heading text>": {"content": [...], "children": [...]}}, ... ]}}

Each entry in a "children" list is a single-key dict whose key IS the heading text and
whose value is {"content": [...], "children": [...]}. "content" is a list of items like
{"type": "text", "content": "..."} (also seen for tables/images with the same "content" key).
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from typing import Any

_MATCH_THRESHOLD = 0.55


def _flatten(children: list[Any]) -> list[tuple[str, dict]]:
    """Recursively flatten a list of single-key heading->node dicts into (heading, node) pairs."""
    result: list[tuple[str, dict]] = []
    for item in children or []:
        if not isinstance(item, dict):
            continue
        for heading, value in item.items():
            if not isinstance(value, dict):
                continue
            result.append((heading, value))
            result.extend(_flatten(value.get('children', [])))
    return result


def _collect_text(node: dict) -> str:
    """Own content text + all descendant sections' text, in document order."""
    parts: list[str] = []
    for item in node.get('content', []) or []:
        if isinstance(item, dict):
            text = item.get('content')
            if isinstance(text, str):
                parts.append(text)
            elif text is not None:
                parts.append(str(text))
    for child_item in node.get('children', []) or []:
        if isinstance(child_item, dict):
            for _, child_value in child_item.items():
                if isinstance(child_value, dict):
                    parts.append(_collect_text(child_value))
    return '\n'.join(p for p in parts if p)


def find_section(tree_json: bytes | str | dict, heading: str) -> tuple[str | None, str | None]:
    """
    Search the tree for the node whose heading best matches `heading` (fuzzy match).

    Returns (matched_heading, section_text) or (None, None) if nothing matched well enough.
    """
    data = json.loads(tree_json) if isinstance(tree_json, (bytes, str)) else tree_json
    root = data.get('root', data) if isinstance(data, dict) else {}
    top_children = root.get('children', []) if isinstance(root, dict) else []
    nodes = _flatten(top_children)

    best_ratio = 0.0
    best_heading: str | None = None
    best_node: dict | None = None
    for node_heading, node_value in nodes:
        ratio = SequenceMatcher(None, node_heading.lower(), heading.lower()).ratio()
        if ratio > best_ratio:
            best_ratio, best_heading, best_node = ratio, node_heading, node_value

    if best_node is None or best_ratio < _MATCH_THRESHOLD:
        return None, None
    return best_heading, _collect_text(best_node)

