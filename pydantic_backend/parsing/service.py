"""Orchestrates parsing a single claimed PDF: submit → poll → fetch → store in Drive."""
from __future__ import annotations

import asyncio

import logfire

from ..config import Settings
from ..ingestion import drive
from .client import ParserClient
from .models import ParseArtifacts, ParseOutcome, ParseStatus, PendingFile
from .repository import ParsingRepository

PARSED_FOLDER_NAME = 'parsed_results'


async def _wait_for_terminal(client: ParserClient, task_id: str, settings: Settings) -> tuple[ParseStatus, str | None]:
    """Poll the parser until the task reaches a terminal state or attempts run out."""
    error: str | None = None
    for _ in range(settings.parse_max_poll_attempts):
        status, error = await client.get_status(task_id)
        if status in (ParseStatus.completed, ParseStatus.failed):
            return status, error
        await asyncio.sleep(settings.parse_poll_interval_seconds)
    return ParseStatus.failed, error or 'Timed out waiting for parser'


async def _store_artifacts(
    settings: Settings, file: PendingFile, client: ParserClient, task_id: str
) -> ParseArtifacts:
    """Download parser outputs and upload them into Drive next to the source PDF."""
    parsed_folder_id = await asyncio.to_thread(
        drive.ensure_subfolder, settings, file.version_folder_id, PARSED_FOLDER_NAME
    )
    stem = file.file_name.rsplit('.', 1)[0]
    entries: dict[str, str] = {}

    # Text/JSON artifacts. Names follow parsed_results/<filename>_* per the spec.
    for suffix, mime, fetch in (
        ('_output_tree.json', 'application/json', client.fetch_tree),
        ('.md', 'text/markdown', client.fetch_markdown),
    ):
        content = await fetch(task_id)
        _, link = await asyncio.to_thread(
            drive.upload_bytes, settings, f'{stem}{suffix}', content, mime, parsed_folder_id
        )
        entries[f'{stem}{suffix}'] = link

    # TOC artifact — upload to Drive and keep parsed JSON for postgres (optional endpoint).
    toc_content = None
    toc_bytes = await client.fetch_toc(task_id)
    if toc_bytes is not None:
        _, toc_link = await asyncio.to_thread(
            drive.upload_bytes, settings, f'{stem}_toc.txt', toc_bytes, 'text/plain', parsed_folder_id
        )
        entries[f'{stem}_toc.txt'] = toc_link
        toc_content = toc_bytes.decode('utf-8', errors='replace')

    # Images → <stem>_images/ subfolder.
    images = await client.fetch_images(task_id)
    images_folder_id: str | None = None
    if images:
        images_folder_id = await asyncio.to_thread(
            drive.ensure_subfolder, settings, parsed_folder_id, f'{stem}_images'
        )
        for name, page, data in images:
            _, link = await asyncio.to_thread(
                drive.upload_bytes, settings, f'page_{page}_{name}', data, 'image/png', images_folder_id
            )
            entries[f'page_{page}_{name}'] = link

    return ParseArtifacts(
        parsed_folder_id=parsed_folder_id,
        images_folder_id=images_folder_id,
        toc_content=toc_content,
        entries=entries,
    )


async def process_file(
    file: PendingFile,
    settings: Settings,
    repository: ParsingRepository,
    client: ParserClient,
) -> ParseOutcome:
    """Parse one already-claimed (PARSING) file and record the outcome."""
    with logfire.span('parsing.process_file', file_id=file.file_id, file_name=file.file_name):
        try:
            content = await asyncio.to_thread(drive.download_file, settings, file.drive_file_id)
            job_id = await client.submit_pdf(file.file_name, content, file.mime_type)
            await repository.set_job_id(file.file_id, job_id)

            status, error = await _wait_for_terminal(client, job_id, settings)
            if status is not ParseStatus.completed:
                message = error or f'Parser reported {status}'
                await repository.mark_failed(file.file_id, message)
                return ParseOutcome(
                    file_id=file.file_id, file_name=file.file_name,
                    status=ParseStatus.failed, parse_job_id=job_id,
                    parse_error=message,
                )

            artifacts = await _store_artifacts(settings, file, client, job_id)
            await repository.mark_parsed(file.file_id, artifacts)
            return ParseOutcome(
                file_id=file.file_id, file_name=file.file_name,
                status=ParseStatus.completed, parse_job_id=job_id,
            )
        except Exception as exc:  # noqa: BLE001 — record and leave for later reprocessing
            logfire.exception('parsing.process_file failed', file_id=file.file_id)
            await repository.mark_failed(file.file_id, str(exc))
            return ParseOutcome(
                file_id=file.file_id, file_name=file.file_name,
                status=ParseStatus.failed, parse_error=str(exc),
            )


async def process_pending(settings: Settings) -> list[ParseOutcome]:
    """Claim a batch of pending files and process them sequentially."""
    repository = ParsingRepository(settings)
    files = await repository.claim_pending_files(settings.parse_batch_size)
    if not files:
        return []
    outcomes: list[ParseOutcome] = []
    async with ParserClient(settings) as client:
        for file in files:
            outcomes.append(await process_file(file, settings, repository, client))
    return outcomes
