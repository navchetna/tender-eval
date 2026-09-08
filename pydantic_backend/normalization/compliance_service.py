"""
Builds the compliance matrix for a project/version by reusing `normalization.service.build_view`
(payment + service) and running each requirement clause through the compliance-judgment LLM
(`evaluation.compliance_client`). Nothing here is persisted — computed fresh on every call, same
as the underlying normalized view.
"""
from __future__ import annotations

from collections import defaultdict

import logfire

from ..evaluation.compliance_client import judge_row
from ..evaluation.models import Topic
from ..evaluation.repository import EvaluationRepository
from ..llm_credentials import LlmCredentials
from . import service as normalization_service
from .models import MatrixData, NormalizedView

_BAND_LABEL = {Topic.payment: 'Payment compliance', Topic.service: 'Service compliance'}
_NO_RESPONSE_CELL = {'s': 'none', 't': 'No response', 'x': '', 'full': ''}
_JUDGMENT_UNAVAILABLE_CELL = {
    's': 'none', 't': 'Not judged', 'x': '',
    'full': 'The compliance model failed to return a verdict for this row — try refreshing.',
}


def _requirement_text(tender_cells: dict[str, str], index: int) -> str:
    parts = [f'{k}: {v}' for k, v in tender_cells.items() if v]
    return ' | '.join(parts) if parts else f'Row {index + 1}'


def _short_ref(tender_cells: dict[str, str], index: int) -> str:
    """Best-guess short reference for the row: the first short-looking tender cell value
    (e.g. a clause/item number), falling back to a plain row number when the tender's table
    has no such column."""
    for value in tender_cells.values():
        if value and len(value) <= 12:
            return value
    return str(index + 1)


def _bidders_from(view: NormalizedView) -> list[str]:
    seen: list[str] = []
    seen_set: set[str] = set()
    for column in view.bid_columns:
        label = column.split(': ', 1)[0]
        if label not in seen_set:
            seen_set.add(label)
            seen.append(label)
    return seen


async def _rows_for_topic(
    creds: LlmCredentials, view: NormalizedView, bidders: list[str]
) -> list[dict]:
    rows: list[dict] = []
    for i, row in enumerate(view.rows):
        requirement = _requirement_text(row.tender_cells, i)
        ref = _short_ref(row.tender_cells, i)

        per_bidder_fields: dict[str, dict[str, str]] = defaultdict(dict)
        for key, value in row.bid_values.items():
            if not value:
                continue
            label, _, field = key.partition(': ')
            per_bidder_fields[label][field] = value

        to_judge = {
            label: ' | '.join(f'{field}: {value}' for field, value in fields.items())
            for label, fields in per_bidder_fields.items()
            if fields
        }
        try:
            verdicts = await judge_row(creds, requirement, to_judge) if to_judge else {}
        except Exception:  # noqa: BLE001 — one bad row must not fail the whole matrix
            logfire.exception('compliance.judge_row failed', requirement=requirement)
            verdicts = {}

        cells = [
            verdicts.get(label, _JUDGMENT_UNAVAILABLE_CELL if label in to_judge else _NO_RESPONSE_CELL)
            for label in bidders
        ]
        rows.append({'ref': ref, 'req': requirement, 'cells': cells})
    return rows


async def build_matrix(
    creds: LlmCredentials,
    circular_repository: EvaluationRepository,
    submission_repository: EvaluationRepository,
    project_id: str,
    version: int,
) -> MatrixData:
    views: dict[Topic, NormalizedView] = {}
    for topic in (Topic.payment, Topic.service):
        try:
            views[topic] = await normalization_service.build_view(
                creds, circular_repository, submission_repository, project_id, version, topic,
            )
        except ValueError:
            continue  # topic not approved/available yet — skip its band entirely

    if not views:
        raise ValueError('Neither payment nor service compliance sections are approved yet for this project/version')

    bidders: list[str] = []
    seen: set[str] = set()
    for view in views.values():
        for label in _bidders_from(view):
            if label not in seen:
                seen.add(label)
                bidders.append(label)

    rows: list[dict] = []
    for topic in (Topic.payment, Topic.service):
        view = views.get(topic)
        if view is None:
            continue
        rows.append({'band': _BAND_LABEL[topic]})
        rows.extend(await _rows_for_topic(creds, view, bidders))

    return MatrixData(project_id=project_id, version=version, bidders=bidders, stale=[], rows=rows)
