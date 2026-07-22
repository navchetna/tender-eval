"""
Orchestrates technical/price section detection: TOC -> Groq -> tree lookup -> store -> notify reviewer.

Works for both tender documents and bid documents — the caller passes in which
EvaluationRepository (tender_repository or bid_repository) to drive.

Flow per pending file:
  1. Read the TOC text already stored on file_repository.parse_toc.
  2. Ask Groq which heading covers technical requirements and which covers price/commercial.
  3. Download the parser's output_tree.json from Drive (via the id captured in parse_artifacts)
     and locate each heading's full section text.
  4. Store the suggestion (status SUGGESTED).
  5. Hand off to the notify_agent, which drafts and sends the reviewer email via a Gmail tool.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

import logfire

from ..config import Settings
from ..ingestion import drive
from . import tree_utils
from .groq_client import detect_sections
from .models import DetectionResult, PendingFile, SectionSuggestion
from .notify_agent import BatchNotifyItem, notify_reviewer, notify_reviewer_batch
from .repository import EvaluationRepository

_TREE_ARTIFACT_SUFFIX = '_output_tree.json'


async def _detect(settings: Settings, file: PendingFile) -> DetectionResult:
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


async def process_pending(settings: Settings, repository: EvaluationRepository) -> list[str]:
    """
    Detect + store for a batch of PARSED files (of repository.doc_type) with no evaluation
    yet, then notify the reviewer. Files in the batch are grouped by (project_id, version)
    so that, e.g., several bid PDFs from the same tender submission trigger a single
    batched reviewer email instead of one email per file.
    """
    files = await repository.claim_pending_files(settings.eval_batch_size)
    created_ids: list[str] = []
    groups: dict[tuple[str, int], list[tuple[str, DetectionResult]]] = defaultdict(list)

    for file in files:
        with logfire.span('evaluation.process_file', file_id=file.file_id):
            try:
                result = await _detect(settings, file)
                evaluation_id = await repository.create_evaluation(file, result.technical, result.price, result.model)
                if evaluation_id is None:
                    continue  # another run already created it (unique file_id constraint)
                created_ids.append(evaluation_id)
                groups[(file.project_id, file.version)].append((file.file_name, evaluation_id, result))
            except Exception:  # noqa: BLE001 — skip this file, keep the batch going
                logfire.exception('evaluation.process_file failed', file_id=file.file_id)

    for (project_id, version), entries in groups.items():
        try:
            if not settings.reviewer_email:
                logfire.warn('evaluation notify skipped: reviewer_email not configured')
                continue
            items = [
                BatchNotifyItem(
                    file_name=file_name, evaluation_id=evaluation_id,
                    technical_heading=result.technical.heading, price_heading=result.price.heading,
                )
                for file_name, evaluation_id, result in entries
            ]
            if await notify_reviewer_batch(settings, project_id, version, items):
                for _, evaluation_id, _ in entries:
                    await repository.mark_notified(evaluation_id)
        except Exception:  # noqa: BLE001 — detections already persisted; notification is best-effort
            logfire.exception('evaluation batch notify failed', project_id=project_id, version=version)

    return created_ids


async def resend_notification(settings: Settings, repository: EvaluationRepository, evaluation_id: str) -> bool:
    """Re-send the reviewer notification for an already-created evaluation (e.g. reviewer_email was unset before)."""
    record = await repository.get_evaluation(evaluation_id)
    if record is None:
        raise ValueError('Evaluation not found')
    sent = await notify_reviewer(
        settings, record.project_id, record.version, record.file_name or f'file {record.file_id}',
        evaluation_id, record.technical_section_title, record.price_section_title,
    )
    if sent:
        await repository.mark_notified(evaluation_id)
    return sent
