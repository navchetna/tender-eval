"""
Locate a TOC heading inside the parser's output_tree.json and pull out that section's
full text content (including nested subsections).

Real schema (confirmed from a live parse):
  {"root": {"content": [...], "children": [ {"<heading text>": {"content": [...], "children": [...]}}, ... ]}}

Each entry in a "children" list is a single-key dict whose key IS the heading text and
whose value is {"content": [...], "children": [...]}. "content" is a list of items like
{"type": "text", "content": "..."} (also seen for tables/images with the same "content" key).

The parser sometimes fails to promote a heading to its own node and instead leaves it
inline in the previous section's text as a markdown "# ..." line (seen live: a page
footer glued in front of the heading kept "3. Service Compliance Self-Certification"
inside the "2. Payment..." node). Two mitigations here, so one topic's section can't
silently swallow the next one's:
  - if a heading matches an inline "#" line better than any node key, the section is
    extracted from that line onward instead of from a (wrong) whole node;
  - callers can pass the *other* sections' headings as `stop_headings`, and extraction
    truncates at the first inline "#" line that matches one of them.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

_MATCH_THRESHOLD = 0.55
# Inline heading lines need a stricter bar than node keys: every line of text is a
# candidate, and running page headers/footers often share most of a heading's words
# (measured live: footer vs heading 0.65, true heading line 1.0).
_LINE_MATCH_THRESHOLD = 0.8


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


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _inline_heading(line: str) -> tuple[str, int] | None:
    """(heading text, markdown level) if this line is an inline "#"-heading, else None."""
    stripped = line.strip()
    if not stripped.startswith('#'):
        return None
    level = len(stripped) - len(stripped.lstrip('#'))
    text = stripped.lstrip('#').strip()
    return (text, level) if text else None


def _truncate_at_stop(text: str, heading: str, stop_headings: Sequence[str]) -> str:
    """Cut `text` at the first inline "#" line that matches one of `stop_headings` better
    than it matches this section's own heading — i.e. the start of a sibling section the
    parser failed to split out."""
    stops = [s for s in stop_headings if s]
    if not stops:
        return text
    lines = text.splitlines()
    for index, line in enumerate(lines):
        parsed = _inline_heading(line)
        if parsed is None:
            continue
        candidate, _ = parsed
        own = _ratio(candidate, heading)
        if any(_ratio(candidate, stop) >= _LINE_MATCH_THRESHOLD and _ratio(candidate, stop) > own for stop in stops):
            return '\n'.join(lines[:index]).rstrip()
    return text


def find_section(
    tree_json: bytes | str | dict, heading: str, stop_headings: Sequence[str] = ()
) -> tuple[str | None, str | None]:
    """
    Search the tree for the node whose heading best matches `heading` (fuzzy match); if an
    inline "#" line inside some node's text matches better than any node key (a heading the
    parser failed to promote — see module docstring), extract from that line onward instead.

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
        ratio = _ratio(node_heading, heading)
        if ratio > best_ratio:
            best_ratio, best_heading, best_node = ratio, node_heading, node_value

    best_line_ratio = 0.0
    best_line_heading: str | None = None
    best_line_text: str | None = None
    # Scan the root's own content too — for some documents (seen live with a long scanned
    # PDF) the parser emits NO hierarchy at all: zero child nodes, the whole text flat in
    # root.content with only inline "#" heading lines to go by.
    scan_nodes = [node_value for _, node_value in nodes]
    if isinstance(root, dict):
        scan_nodes.append(root)
    for node_value in scan_nodes:
        lines = _collect_text(node_value).splitlines()
        for index, line in enumerate(lines):
            parsed = _inline_heading(line)
            if parsed is None:
                continue
            candidate, level = parsed
            ratio = _ratio(candidate, heading)
            if ratio > best_line_ratio:
                # The section runs until the next inline heading of the same or a higher
                # level — without this bound, a match inside a flat tree would swallow the
                # whole rest of the document.
                end = len(lines)
                for j in range(index + 1, len(lines)):
                    later = _inline_heading(lines[j])
                    if later is not None and later[1] <= level:
                        end = j
                        break
                best_line_ratio = ratio
                best_line_heading = candidate
                best_line_text = '\n'.join(lines[index + 1 : end]).strip()

    if best_line_ratio >= _LINE_MATCH_THRESHOLD and best_line_ratio > best_ratio:
        assert best_line_heading is not None and best_line_text is not None
        return best_line_heading, _truncate_at_stop(best_line_text, best_line_heading, stop_headings)

    if best_node is None or best_ratio < _MATCH_THRESHOLD:
        return None, None
    return best_heading, _truncate_at_stop(_collect_text(best_node), best_heading or heading, stop_headings)

