"""
Orchestrates technical/price section detection: TOC -> LiteLLM -> tree lookup -> store -> notify reviewer.

Works for both tender documents and bid documents — the caller passes in which
EvaluationRepository (tender_repository or bid_repository) to drive.

Flow per pending file:
  1. Read the TOC text already stored on file_repository.parse_toc.
  2. Ask the LLM which heading covers technical requirements and which covers price/commercial.
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
from ..llm_credentials import LlmCredentials
from . import tree_utils
from .detection_client import detect_sections
from .models import DetectionResult, PendingFile, SectionSuggestion
from .notify_agent import BatchNotifyItem, notify_reviewer, notify_reviewer_batch
from .repository import EvaluationRepository

_TREE_ARTIFACT_SUFFIX = '_output_tree.json'


async def _detect(creds: LlmCredentials, settings: Settings, file: PendingFile) -> DetectionResult:
    toc_text = file.parse_toc or ''
    technical_heading, price_heading = (None, None)
    if toc_text.strip():
        technical_heading, price_heading = await detect_sections(creds, toc_text)

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
        model=creds.model,
    )


async def detect_and_store(
    creds: LlmCredentials, settings: Settings, repository: EvaluationRepository, file: PendingFile
) -> tuple[str, DetectionResult] | None:
    """
    Detect + persist a SUGGESTED evaluation for one file — the shared building block behind
    the inline trigger (right after this file's own parse completes, see parsing/service.py),
    the periodic catch-up pass in `process_pending`, and the manual `retry_file` endpoint.
    Never raises: a failure here is recorded on `detection_error` and reported as None, since
    callers must not let a detection failure look like the parse (or the rest of a batch)
    failed. Returns None if detection failed, or if another run already created the evaluation
    for this file first (the unique file_id constraint) — either way, there's nothing new to
    notify about.
    """
    try:
        await repository.set_detection_error(file.file_id, None)
        result = await _detect(creds, settings, file)
        evaluation_id = await repository.create_evaluation(file, result.technical, result.price, result.model)
        if evaluation_id is None:
            return None
        return evaluation_id, result
    except Exception as exc:  # noqa: BLE001 — caller keeps going; this file's error is recorded
        logfire.exception('evaluation.detect_and_store failed', file_id=file.file_id)
        try:
            await repository.set_detection_error(file.file_id, str(exc))
        except Exception:  # noqa: BLE001 — best-effort; must not raise out of here
            logfire.exception('evaluation.set_detection_error failed', file_id=file.file_id)
        return None


async def process_pending(creds: LlmCredentials, settings: Settings, repository: EvaluationRepository) -> list[str]:
    """
    Two independent passes, run every worker tick:

      1. Catch-up detection for PARSED files (of repository.doc_type) with no evaluation yet —
         a safety net for files whose inline detection (triggered right after their own parse
         completes, see parsing/service.py) never ran or failed, e.g. a crash between marking
         the file PARSED and detecting it.
      2. Notify sweep: batch-notify the reviewer for every evaluation that exists but hasn't
         been notified yet, grouped by (project_id, version) so several bid PDFs from the same
         tender submission still produce one email. Deliberately decoupled from step 1's
         claim query — most evaluations these days were created inline right after parsing,
         not by step 1, and still need this sweep to actually get notified.
    """
    files = await repository.claim_pending_files(settings.eval_batch_size)
    created_ids: list[str] = []
    for file in files:
        with logfire.span('evaluation.process_file', file_id=file.file_id):
            detected = await detect_and_store(creds, settings, repository, file)
            if detected is not None:
                created_ids.append(detected[0])

    unnotified = await repository.list_unnotified(settings.eval_batch_size)
    groups: dict[tuple[str, int], list[BatchNotifyItem]] = defaultdict(list)
    for row in unnotified:
        groups[(str(row['project_id']), row['version'])].append(
            BatchNotifyItem(
                file_name=row['file_name'], evaluation_id=str(row['evaluation_id']),
                technical_heading=row['technical_section_title'], price_heading=row['price_section_title'],
            )
        )

    for (project_id, version), items in groups.items():
        try:
            if not settings.reviewer_email:
                logfire.warn('evaluation notify skipped: reviewer_email not configured')
                continue
            if await notify_reviewer_batch(creds, settings, project_id, version, items):
                for item in items:
                    await repository.mark_notified(item.evaluation_id)
        except Exception:  # noqa: BLE001 — detections already persisted; notification is best-effort
            logfire.exception('evaluation batch notify failed', project_id=project_id, version=version)

    return created_ids


async def retry_file(
    creds: LlmCredentials, settings: Settings, repository: EvaluationRepository, file_id: str
) -> str | None:
    """
    Manually retry section detection for one specific file, then notify immediately for just
    this file (unlike the periodic sweep's batched-per-submission email — a manual retry is an
    explicit single-file action, so immediate single-file feedback is what the caller wants).
    Raises ValueError if the file isn't PARSED or already has an evaluation. Returns the new
    evaluation_id, or None if detection failed again (the new error is left on
    `detection_error` for the caller to surface — failing isn't itself an error condition
    here, since the point of a retry is that it might fail the same way).
    """
    file = await repository.get_file_for_retry(file_id)
    if file is None:
        raise ValueError('File is not eligible for section-detection retry')

    detected = await detect_and_store(creds, settings, repository, file)
    if detected is None:
        return None
    evaluation_id, result = detected

    try:
        if settings.reviewer_email and await notify_reviewer(
            creds, settings, file.project_id, file.version, file.file_name,
            evaluation_id, result.technical.heading, result.price.heading,
        ):
            await repository.mark_notified(evaluation_id)
    except Exception:  # noqa: BLE001 — detection already persisted; notification is best-effort
        logfire.exception('evaluation.retry_file notify failed', file_id=file_id)
    return evaluation_id


async def resend_notification(
    creds: LlmCredentials, settings: Settings, repository: EvaluationRepository, evaluation_id: str
) -> bool:
    """Re-send the reviewer notification for an already-created evaluation (e.g. reviewer_email was unset before)."""
    record = await repository.get_evaluation(evaluation_id)
    if record is None:
        raise ValueError('Evaluation not found')
    sent = await notify_reviewer(
        creds, settings, record.project_id, record.version, record.file_name or f'file {record.file_id}',
        evaluation_id, record.technical_section_title, record.price_section_title,
    )
    if sent:
        await repository.mark_notified(evaluation_id)
    return sent
