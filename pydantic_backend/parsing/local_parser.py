"""
In-process PDF parser (`model_runtime='inprocess'`) — a drop-in for `ParserClient` that replaces
the separate docling `pdf-pipeline` service + llama.cpp LightOnOCR server.

It produces the same artifacts that service does, in the same shapes, so parsing/service.py,
evaluation/tree_utils.py and normalization/table_utils.py consume them unchanged:

  - `<stem>.md`               page-by-page OCR Markdown (HTML tables converted to pipe tables)
  - `<stem>_output_tree.json` {"root": {"content": [...], "children": [{heading: {...}}, ...]}}
  - `<stem>_toc.txt`          one "level;heading" line per TOC entry
  - figures                   embedded raster images, as (name, page, png_bytes)

Pipeline per PDF: render each page (pypdfium2) → drop near-blank pages (same heuristic as the
service) → OCR each page with the in-process LightOnOCR-3 VLM (local_models/ocr.py) → derive the
TOC from the OCR'd headings → build the section tree with the service's tree-parser algorithm
(ported below, minus its docling/torch dependency).

The service's TOC came from a second docling layout-model pass; here it comes from the VLM's own
Markdown headings instead, using the same rule the service applied to docling's headings:
numbered headings ("3.1 Hardware") define the TOC and their depth when any exist, otherwise the
Markdown heading level is used.
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html.parser import HTMLParser

import logfire_api as logfire

from ..config import Settings
from .models import ParseStatus

# Blank-page detection — identical thresholds to the docling service's pre-filter.
_BLANK_DETECT_SCALE = 1.0
_BLANK_MEAN_MIN = 245
_BLANK_STDDEV_MAX = 8
_MIN_MARKDOWN_CHARS = 32
_MIN_FIGURE_EDGE_PX = 64

_LEVEL_PATTERN = re.compile(r'^\d+(\.\d+)*\.?\s')
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)')
_CAPTION_RE = re.compile(r'^(Table|Figure)\s+(\d+)', re.IGNORECASE)
_SPAN_RE = re.compile(r'<span[^>]*?/?>(</span>)?')
_TABLE_BLOCK_RE = re.compile(r'<table\b.*?</table>', re.IGNORECASE | re.DOTALL)
_IMAGE_PLACEHOLDER_RE = re.compile(r'^\s*!\[[^\]]*\]\([^)]*\)\s*$', re.MULTILINE)
_WRAPPER_TAG_RE = re.compile(r'^\s*</?(div|center|p)\b[^>]*>\s*$', re.IGNORECASE | re.MULTILINE)


# --------------------------------------------------------------------------------------------
# OCR output clean-up
# --------------------------------------------------------------------------------------------

class _TableHTML(HTMLParser):
    """Collects an HTML <table> into a rectangular grid, expanding colspan/rowspan by repeating
    the cell text — the same way the service's docling export renders merged cells."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, int, int]]] = []
        self._cell: list[str] | None = None
        self._span = (1, 1)

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.rows.append([])
        elif tag in ('td', 'th'):
            if not self.rows:
                self.rows.append([])
            attributes = dict(attrs)
            self._cell = []
            self._span = (_int(attributes.get('colspan')), _int(attributes.get('rowspan')))
        elif tag == 'br' and self._cell is not None:
            self._cell.append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None:
            text = ' '.join(''.join(self._cell).split()).replace('|', '/')
            self.rows[-1].append((text, *self._span))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _int(value: str | None) -> int:
    try:
        return max(1, int(value or 1))
    except ValueError:
        return 1


def _html_table_to_pipe(html: str) -> str:
    parser = _TableHTML()
    parser.feed(html)
    grid: list[list[str]] = []
    carried: dict[tuple[int, int], str] = {}  # (row, col) -> text from a rowspan above
    for r, row in enumerate(parser.rows):
        out: list[str] = []
        col = 0
        cells = iter(row)
        pending = next(cells, None)
        while pending is not None or (r, col) in carried:
            if (r, col) in carried:
                out.append(carried.pop((r, col)))
                col += 1
                continue
            text, colspan, rowspan = pending
            for c in range(colspan):
                out.append(text)
                for extra in range(1, rowspan):
                    carried[(r + extra, col + c)] = text
            col += colspan
            pending = next(cells, None)
        grid.append(out)
    grid = [row for row in grid if any(cell for cell in row)]
    if not grid:
        return ''
    width = max(len(row) for row in grid)
    grid = [row + [''] * (width - len(row)) for row in grid]
    lines = ['| ' + ' | '.join(grid[0]) + ' |', '|' + '---|' * width]
    lines += ['| ' + ' | '.join(row) + ' |' for row in grid[1:]]
    return '\n'.join(lines)


def clean_page_markdown(markdown: str) -> str:
    markdown = _TABLE_BLOCK_RE.sub(lambda m: '\n\n' + _html_table_to_pipe(m.group(0)) + '\n\n', markdown)
    markdown = _IMAGE_PLACEHOLDER_RE.sub('', markdown)
    markdown = _WRAPPER_TAG_RE.sub('', markdown)
    # The model indents TOC/list lines with &nbsp; runs; downstream text matching wants spaces.
    markdown = markdown.replace('&nbsp;', ' ')
    return re.sub(r'\n{3,}', '\n\n', markdown).strip()


# --------------------------------------------------------------------------------------------
# TOC + tree (port of navchetna/tree-parser's TreeParser, which the docling service runs)
# --------------------------------------------------------------------------------------------

def build_toc(markdown: str) -> list[tuple[int, str]]:
    headings = []
    for line in markdown.splitlines():
        match = _HEADING_RE.match(_SPAN_RE.sub('', line))
        if match:
            headings.append((len(match.group(1)), match.group(2).strip().replace('*', '')))
    if any(_LEVEL_PATTERN.match(title) for _, title in headings):
        return [
            (title.split(' ', 1)[0].rstrip('.').count('.') + 1, title)
            for _, title in headings if _LEVEL_PATTERN.match(title)
        ]
    return headings


def toc_text(toc: list[tuple[int, str]]) -> str:
    return ''.join(f'{level};{title}\n' for level, title in toc)


@dataclass
class _Node:
    level: int
    heading: str
    content: list[dict] = field(default_factory=list)
    children: list['_Node'] = field(default_factory=list)

    def to_json(self) -> dict:
        return {self.heading: {'content': self.content, 'children': [c.to_json() for c in self.children]}}


def build_tree(markdown: str, toc: list[tuple[int, str]]) -> dict:
    """Section tree keyed by heading. When a TOC exists, only Markdown headings that match the
    next TOC entry (in order, fuzzy) open a section — any other heading stays as body text — and
    the section's depth comes from the TOC. Without a TOC every Markdown heading opens a section."""
    root = _Node(0, 'root')
    recent: dict[int, _Node] = {0: root}
    toc_entries = [entry for entry in toc if entry[1].strip()]
    toc_index = 0
    use_markdown_headings = not toc_entries
    current = root
    text = ''
    lines = [_SPAN_RE.sub('', line) for line in markdown.splitlines()]

    def flush() -> None:
        nonlocal text
        if text:
            current.content.append({'type': 'text', 'content': text})
            text = ''

    def attach(level: int, heading: str) -> None:
        nonlocal current
        node = _Node(level, heading)
        parent_level = max((lvl for lvl in recent if lvl < level), default=0)
        recent[parent_level].children.append(node)
        for lvl in [lvl for lvl in recent if lvl >= level]:
            del recent[lvl]
        recent[level] = node
        current = node

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        match = _HEADING_RE.match(line)
        if match:
            heading = match.group(2).strip().replace('*', '')
            if not use_markdown_headings and toc_index < len(toc_entries):
                level, toc_heading = toc_entries[toc_index]
                if SequenceMatcher(None, 'contents', toc_heading.lower()).ratio() > 0.6:
                    toc_index += 1
                    if toc_index < len(toc_entries):
                        level, toc_heading = toc_entries[toc_index]
            if not use_markdown_headings and toc_index >= len(toc_entries):
                use_markdown_headings = True  # TOC exhausted: fall back for the rest
            if use_markdown_headings:
                flush()
                attach(len(match.group(1)), heading)
            elif SequenceMatcher(None, heading.lower(), toc_heading.lower()).ratio() > 0.6:
                flush()
                attach(level, heading)
                toc_index += 1
            else:
                text += line + '\n'
        elif line.startswith('|'):
            flush()
            table = [line]
            while i + 1 < len(lines) and lines[i + 1].startswith('|'):
                i += 1
                table.append(lines[i])
            # tree-parser also detects a "Table N"/"Figure N" caption next to the table, but never
            # serializes it into output_tree.json, so it isn't tracked here; caption lines are
            # dropped from body text below, as there.
            current.content.append({'type': 'table', 'content': '\n'.join(table) + '\n'})
        elif not _CAPTION_RE.search(line):
            text += line + '\n'
        i += 1
    flush()
    return root.to_json()


# --------------------------------------------------------------------------------------------
# PDF → artifacts
# --------------------------------------------------------------------------------------------

@dataclass
class LocalParseResult:
    markdown: bytes
    tree: bytes
    toc: bytes
    images: list[tuple[str, int, bytes]]
    total_pages: int
    kept_pages: int


def _is_blank(page) -> bool:
    from PIL import ImageStat

    stat = ImageStat.Stat(page.render(scale=_BLANK_DETECT_SCALE).to_pil().convert('L'))
    return stat.mean[0] > _BLANK_MEAN_MIN and stat.stddev[0] < _BLANK_STDDEV_MAX


def _figures(page, page_no: int, counter: list[int]) -> list[tuple[str, int, bytes]]:
    import pypdfium2.raw as pdfium_c

    found: list[tuple[str, int, bytes]] = []
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
        try:
            image = obj.get_bitmap(render=True).to_pil()
        except Exception:  # noqa: BLE001 — undecodable image streams are skipped, not fatal
            continue
        if min(image.size) < _MIN_FIGURE_EDGE_PX:
            continue
        counter[0] += 1
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        found.append((f'figure_{counter[0]}.png', page_no, buffer.getvalue()))
    return found


def parse_pdf(content: bytes) -> LocalParseResult:
    """Blocking: run the whole PDF through render → OCR → TOC/tree. Raises on failure."""
    import pypdfium2 as pdfium

    from ..local_models import ocr

    pdf = pdfium.PdfDocument(content)
    pages_md: list[str] = []
    images: list[tuple[str, int, bytes]] = []
    figure_counter = [0]
    kept = 0
    try:
        total = len(pdf)
        for index in range(total):
            page = pdf[index]
            try:
                if _is_blank(page):
                    continue
                kept += 1
                images.extend(_figures(page, index + 1, figure_counter))
                width, height = page.get_size()
                rendered = page.render(scale=ocr.RENDER_LONGEST_EDGE / max(width, height)).to_pil()
                with logfire.span('local_parser.ocr_page', page=index + 1):
                    pages_md.append(clean_page_markdown(ocr.page_to_markdown(rendered)))
            finally:
                page.close()
    finally:
        pdf.close()

    if not kept:
        raise RuntimeError(f'All {total} pages classified as blank')
    markdown = '\n\n'.join(md for md in pages_md if md) + '\n'
    if len(markdown.strip()) < _MIN_MARKDOWN_CHARS:
        raise RuntimeError(f'OCR produced empty/too-small markdown ({len(markdown)} chars)')
    toc = build_toc(markdown)
    tree = build_tree(markdown, toc)
    return LocalParseResult(
        markdown=markdown.encode('utf-8'),
        tree=json.dumps(tree).encode('utf-8'),
        toc=toc_text(toc).encode('utf-8'),
        images=images,
        total_pages=total,
        kept_pages=kept,
    )


class LocalParserClient:
    """Same interface as parsing.client.ParserClient, so parsing/service.py can use either.
    "Submitting" starts the parse in a worker thread; `get_status` waits for it to finish
    rather than being polled on a timer, so a long PDF is never cut off by
    parse_max_poll_attempts the way a remote job could be."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tasks: dict[str, asyncio.Task[LocalParseResult]] = {}

    async def __aenter__(self) -> 'LocalParserClient':
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

    async def submit_pdf(self, file_name: str, content: bytes, mime_type: str) -> str:
        task_id = f'local-{uuid.uuid4()}'
        self._tasks[task_id] = asyncio.create_task(asyncio.to_thread(parse_pdf, content))
        return task_id

    async def get_status(self, task_id: str) -> tuple[ParseStatus, str | None]:
        task = self._tasks[task_id]
        try:
            await asyncio.shield(task)
        except Exception as exc:  # noqa: BLE001 — reported to the caller as a failed parse
            return ParseStatus.failed, str(exc) or exc.__class__.__name__
        return ParseStatus.completed, None

    async def fetch_markdown(self, task_id: str) -> bytes:
        return self._tasks[task_id].result().markdown

    async def fetch_tree(self, task_id: str) -> bytes:
        return self._tasks[task_id].result().tree

    async def fetch_toc(self, task_id: str) -> bytes | None:
        return self._tasks[task_id].result().toc

    async def fetch_images(self, task_id: str) -> list[tuple[str, int, bytes]]:
        return self._tasks[task_id].result().images
