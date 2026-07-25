"""
Builds the per-file "what actually happened at this stage" view backing the workspace's
stage-detail popover (see /projects/{project_id}/files/{file_id}/stage-detail in app.py).
Pairs with the static schemas from GET /pipeline/schema — this module supplies the *actual*
input/output values for one file, not the shape those values are documented against.

"Aligned" (the 5th stage in the frontend's ladder) has no entry here — it's a derived readiness
flag depending on the *other* file's approval status, not a processing stage with its own
input/output; the frontend renders it entirely from data it already has.
"""
from __future__ import annotations

from pydantic import BaseModel

from .evaluation.models import EvaluationRecord


class StageDetail(BaseModel):
    input: dict | None = None
    output: dict | None = None
    error: str | None = None


class FileStageDetail(BaseModel):
    received: StageDetail
    parsed: StageDetail
    sections: StageDetail
    clauses: StageDetail


def _received_detail(file: dict) -> StageDetail:
    return StageDetail(
        input={
            'message_id': file.get('email_message_id'),
            'sender': file.get('email_from'),
            'subject': file.get('email_subject'),
            'received_at': _isoformat(file.get('email_received_at')),
        },
        output={
            'file_id': str(file['file_id']),
            'file_name': file['file_name'],
            'file_type': file['file_type'],
            'processing_status': file['processing_status'],
            'drive_file_id': file.get('drive_file_id'),
            'drive_web_link': file.get('drive_web_link'),
        },
    )


def _parsed_detail(file: dict) -> StageDetail:
    if file['processing_status'] not in ('PARSED', 'PARSE_FAILED'):
        return StageDetail()
    return StageDetail(
        input={
            'file_id': str(file['file_id']),
            'file_name': file['file_name'],
            'drive_file_id': file.get('drive_file_id'),
            'mime_type': file.get('mime_type'),
        },
        output={
            'parse_toc': file.get('parse_toc'),
            'parse_artifacts': file.get('parse_artifacts'),
        } if file['processing_status'] == 'PARSED' else None,
        error=file.get('parse_error'),
    )


def _sections_detail(file: dict, evaluation: EvaluationRecord | None) -> StageDetail:
    if file['processing_status'] != 'PARSED' and evaluation is None:
        return StageDetail(error=file.get('detection_error'))
    return StageDetail(
        input={
            'file_id': str(file['file_id']),
            'file_name': file['file_name'],
            'parse_toc': file.get('parse_toc'),
        },
        output={
            # The immutable AI snapshot, not the (possibly human-corrected) current value —
            # this is what detection actually produced, before any review happened.
            'technical': {'heading': evaluation.technical_ai_title, 'content': evaluation.technical_ai_content},
            'price': {'heading': evaluation.price_ai_title, 'content': evaluation.price_ai_content},
            'model': evaluation.detection_model,
        } if evaluation is not None else None,
        error=file.get('detection_error'),
    )


def _clauses_detail(evaluation: EvaluationRecord | None) -> StageDetail:
    if evaluation is None:
        return StageDetail()
    return StageDetail(
        input={
            'technical': {'heading': evaluation.technical_ai_title, 'content': evaluation.technical_ai_content},
            'price': {'heading': evaluation.price_ai_title, 'content': evaluation.price_ai_content},
        },
        output={
            'technical': {
                'heading': evaluation.technical_section_title, 'status': evaluation.technical_status,
                'corrected': evaluation.technical_corrected, 'reviewed_by': evaluation.technical_reviewed_by,
                'reviewed_at': _isoformat(evaluation.technical_reviewed_at),
            },
            'price': {
                'heading': evaluation.price_section_title, 'status': evaluation.price_status,
                'corrected': evaluation.price_corrected, 'reviewed_by': evaluation.price_reviewed_by,
                'reviewed_at': _isoformat(evaluation.price_reviewed_at),
            },
        },
    )


def _isoformat(value: object) -> str | None:
    return value.isoformat() if hasattr(value, 'isoformat') else value


def build_file_stage_detail(file: dict, evaluation: EvaluationRecord | None) -> FileStageDetail:
    return FileStageDetail(
        received=_received_detail(file),
        parsed=_parsed_detail(file),
        sections=_sections_detail(file, evaluation),
        clauses=_clauses_detail(evaluation),
    )
