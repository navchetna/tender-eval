"""
Orchestrates tender section detection: TOC -> Groq -> tree lookup -> store -> notify reviewer.

Flow per pending tender file:
  1. Read the TOC text already stored on file_repository.parse_toc.
  2. Ask Groq which heading covers technical requirements and which covers price/commercial.
  3. Download the parser's output_tree.json from Drive (via the id captured in parse_artifacts)
     and locate each heading's full section text.
  4. Store the suggestion in tender_evaluations (status SUGGESTED).
  5. Hand off to the notify_agent, which drafts and sends the reviewer email via a Gmail tool.
"""
from __future__ import annotations

import asyncio

import logfire

from ..config import Settings
from ..ingestion import drive
from . import tree_utils
from .groq_client import detect_sections
from .models import DetectionResult, PendingTenderFile, SectionSuggestion
from .notify_agent import notify_reviewer
from .repository import EvaluationRepository

_TREE_ARTIFACT_SUFFIX = '_output_tree.json'


async def _detect(settings: Settings, file: PendingTenderFile) -> DetectionResult:
    toc_text = file.parse_toc or ''
    technical_heading, price_heading = (None, None)
    if toc_text.strip():
        technical_heading, price_heading = await detect_sections(settings, toc_text)

    tree_bytes: bytes | None = None
    artifacts = file.parse_artifacts or {}
    entries = artifacts.get('entries') or {}
    tree_entry = next((v for k, v in entries.items() if k.endswith(_TREE_ARTIFACT_SUFFIX)), None)
    if tree_entry and tree_entry.get('id'):
        tree_bytes = await asyncio.to_thread(drive.download_file, settings, tree_entry['id'])

    def _resolve(heading: str | None) -> SectionSuggestion:
        if not heading:
            return SectionSuggestion()
        if tree_bytes is None:
            return SectionSuggestion(heading=heading, matched=False)
        matched_heading, content = tree_utils.find_section(tree_bytes, heading)
        if matched_heading is None:
            return SectionSuggestion(heading=heading, matched=False)
        return SectionSuggestion(heading=matched_heading, content=content, matched=True)

    return DetectionResult(
        technical=_resolve(technical_heading),
        price=_resolve(price_heading),
        model=settings.groq_model,
    )


async def process_pending(settings: Settings) -> list[str]:
    """Detect + store + notify for a batch of PARSED tender files with no evaluation yet."""
    repository = EvaluationRepository(settings)
    files = await repository.claim_pending_tender_files(settings.eval_batch_size)
    created_ids: list[str] = []
    for file in files:
        with logfire.span('evaluation.process_file', file_id=file.file_id):
            try:
                result = await _detect(settings, file)
                evaluation_id = await repository.create_evaluation(file, result.technical, result.price, result.model)
                if evaluation_id is None:
                    continue  # another run already created it (unique file_id constraint)
                try:
                    if not settings.reviewer_email:
                        logfire.warn('evaluation notify skipped: reviewer_email not configured')
                    elif await notify_reviewer(
                        settings, file.project_id, file.version, file.file_name,
                        evaluation_id, result.technical.heading, result.price.heading,
                    ):
                        await repository.mark_notified(evaluation_id)
                except Exception:  # noqa: BLE001 — detection already persisted; notification is best-effort
                    logfire.exception('evaluation notify failed', evaluation_id=evaluation_id)
                created_ids.append(evaluation_id)
            except Exception:  # noqa: BLE001 — skip this file, keep the batch going
                logfire.exception('evaluation.process_file failed', file_id=file.file_id)
    return created_ids


async def resend_notification(settings: Settings, evaluation_id: str) -> bool:
    """Re-send the reviewer notification for an already-created evaluation (e.g. reviewer_email was unset before)."""
    repository = EvaluationRepository(settings)
    record = await repository.get_evaluation(evaluation_id)
    if record is None:
        raise ValueError('Evaluation not found')
    sent = await notify_reviewer(
        settings, record.project_id, record.version, f'file {record.file_id}',
        evaluation_id, record.technical_section_title, record.price_section_title,
    )
    if sent:
        await repository.mark_notified(evaluation_id)
    return sent
