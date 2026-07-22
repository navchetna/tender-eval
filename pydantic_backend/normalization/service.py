"""
Builds the on-demand tender-vs-bid comparison view. Nothing here is persisted \u2014 it re-reads
tender_evaluations/bid_evaluations (via EvaluationRepository) and computes the merged view
fresh on every call.
"""
from __future__ import annotations

import os

from ..config import Settings
from ..evaluation.models import EvaluationRecord, Topic
from ..evaluation.repository import EvaluationRepository
from . import table_utils
from .align_client import match_headers, match_rows
from .models import NormalizedRow, NormalizedView


def _content_for(record: EvaluationRecord, topic: Topic) -> tuple[str | None, str]:
    if topic is Topic.technical:
        return record.technical_section_content, record.technical_status
    return record.price_section_content, record.price_status


def _bid_label(record: EvaluationRecord, used: set[str]) -> str:
    stem = os.path.splitext(record.file_name or record.file_id)[0]
    label = stem
    suffix = 2
    while label in used:
        label = f'{stem} ({suffix})'
        suffix += 1
    used.add(label)
    return label


def _bid_columns_of(rows: list[dict]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row['cells']:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns


def _bid_row_fields(
    tender_cells: dict[str, str], bid_cells: dict[str, str], header_mapping: dict[str, str | None]
) -> dict[str, str]:
    """
    Map one matched bid row onto output field names, using the (LLM-derived) header_mapping.

    - A bid column mapped to a tender column left EMPTY for this row (e.g. tender's blank
      "Unit Cost"/"Total Cost" template columns) is filled in under that tender column's name,
      so it lines up as if the tender itself had reported it.
    - A bid column mapped to a tender column that's already non-empty (e.g. "Item", "Unit of
      Measure") is skipped \u2014 the tender already answers that field, no need to duplicate.
    - A bid column with no tender-column mapping at all (e.g. "Compliance Status", which the
      tender's table doesn't have a column for) is kept under its own bid header name.
    """
    fields: dict[str, str] = {}
    for bid_header, bid_value in bid_cells.items():
        if not bid_value:
            continue
        matched_column = header_mapping.get(bid_header)
        if matched_column and tender_cells.get(matched_column):
            continue  # tender already specifies this field
        fields[matched_column or bid_header] = bid_value
    return fields


async def build_view(
    settings: Settings,
    tender_repository: EvaluationRepository,
    bid_repository: EvaluationRepository,
    project_id: str,
    version: int,
    topic: Topic,
) -> NormalizedView:
    tender_records = await tender_repository.list_by_project_version(project_id, version)
    if not tender_records:
        raise ValueError('No tender evaluation found for this project/version')
    tender_record = tender_records[0]
    tender_content, tender_status = _content_for(tender_record, topic)
    if tender_status != 'APPROVED':
        raise ValueError(f'Tender {topic.value} section has not been approved yet (status={tender_status})')

    tender_rows = table_utils.parse_rows(tender_content or '')
    tender_texts = [row['text'] for row in tender_rows]

    tender_columns: list[str] = []
    seen_columns: set[str] = set()
    for row in tender_rows:
        for key in row['cells']:
            if key not in seen_columns:
                seen_columns.add(key)
                tender_columns.append(key)

    bid_records = await bid_repository.list_by_project_version(project_id, version)
    used_labels: set[str] = set()
    # bid_label -> ordered field names that bid actually contributed (across all its rows)
    bid_fields_by_label: dict[str, list[str]] = {}
    # tender row index -> bid_label -> {field: value}
    per_row_bid_fields: list[dict[str, dict[str, str]]] = [dict() for _ in tender_rows]

    for bid_record in bid_records:
        bid_content, bid_status = _content_for(bid_record, topic)
        if bid_status != 'APPROVED':
            continue  # skip bids whose section hasn't been human-approved yet
        label = _bid_label(bid_record, used_labels)

        bid_rows = table_utils.parse_rows(bid_content or '')
        bid_texts = [row['text'] for row in bid_rows]
        bid_header_list = _bid_columns_of(bid_rows)
        header_mapping = await match_headers(settings, tender_columns, bid_header_list) if bid_header_list and tender_columns else {}
        indices = await match_rows(settings, tender_texts, bid_texts) if tender_texts else []

        fields_seen: list[str] = []
        for i, bid_index in enumerate(indices):
            if bid_index is None:
                continue
            fields = _bid_row_fields(tender_rows[i]['cells'], bid_rows[bid_index]['cells'], header_mapping)
            per_row_bid_fields[i][label] = fields
            for field in fields:
                if field not in fields_seen:
                    fields_seen.append(field)
        bid_fields_by_label[label] = fields_seen

    bid_columns: list[str] = [
        f'{label}: {field}' for label, fields in bid_fields_by_label.items() for field in fields
    ]

    # Drop tender columns that are empty across every row (blank bidder-fill-in templates like
    # "Unit Cost"/"Total Cost") from the output \u2014 the bidder's own values (in bid_columns) already
    # cover that data, so an all-blank tender column adds nothing to the comparison view.
    visible_tender_columns = [
        col for col in tender_columns if any(row['cells'].get(col) for row in tender_rows)
    ]

    rows = []
    for i in range(len(tender_texts)):
        bid_values: dict[str, str | None] = {}
        for label, fields in bid_fields_by_label.items():
            row_fields = per_row_bid_fields[i].get(label, {})
            for field in fields:
                bid_values[f'{label}: {field}'] = row_fields.get(field)
        rows.append(NormalizedRow(
            tender_cells={col: tender_rows[i]['cells'].get(col, '') for col in visible_tender_columns},
            bid_values=bid_values,
        ))

    return NormalizedView(
        project_id=project_id,
        version=version,
        topic=topic,
        tender_file_name=tender_record.file_name,
        tender_columns=visible_tender_columns,
        bid_columns=bid_columns,
        rows=rows,
    )
