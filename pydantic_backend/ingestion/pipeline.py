from pathlib import PurePosixPath

import logfire

from ..config import Settings
from .drive import ensure_project_folder, upload_attachment
from .models import Attachment, DriveContext, IncomingEmail, IngestionResult, StageResult
from .postgres import PostgresRepository
from .subject import parse_subject


class AlreadyIngestedError(Exception):
    pass


def _dedupe_attachment_names(attachments: list[Attachment]) -> list[Attachment]:
    """
    A single email carrying one tender + multiple bidder PDFs can legitimately contain
    two attachments with the identical file_name (e.g. two bidders both attach "bid.pdf").
    Downstream, both the Drive-upload dict (keyed by file_name) and the Postgres
    `UNIQUE (email_message_id, file_name)` constraint key off this name, so an unmodified
    duplicate would silently overwrite/drop the earlier attachment. Rename the 2nd+
    occurrence in-memory (before anything is uploaded or persisted) to keep every
    attachment distinct: "bid.pdf" -> "bid (2).pdf" -> "bid (3).pdf", etc.
    """
    seen_counts: dict[str, int] = {}
    deduped: list[Attachment] = []
    for attachment in attachments:
        count = seen_counts.get(attachment.file_name, 0) + 1
        seen_counts[attachment.file_name] = count
        if count == 1:
            deduped.append(attachment)
        else:
            path = PurePosixPath(attachment.file_name)
            new_name = f'{path.stem} ({count}){path.suffix}'
            deduped.append(attachment.model_copy(update={'file_name': new_name}))
    return deduped


async def persist_gmail_email(
    email: IncomingEmail,
    repository: PostgresRepository,
    settings: Settings,
) -> IngestionResult:
    """Stages: validate → parse subject → resolve version → create Drive folders → upload PDFs → persist to Postgres."""
    stages: list[StageResult] = []

    with logfire.span('ingestion.01.validate_email', message_id=email.message_id):
        if not email.attachments:
            raise ValueError('Email contains no PDF attachments')
        if await repository.is_already_ingested(email.message_id):
            raise AlreadyIngestedError(f'Email {email.message_id} already ingested; skipping')
        email = email.model_copy(update={'attachments': _dedupe_attachment_names(email.attachments)})
        stages.append(StageResult(stage='01_validate_email', status='completed'))

    with logfire.span('ingestion.02.parse_subject'):
        project = parse_subject(email.subject)
        stages.append(StageResult(stage='02_parse_subject', status='completed', detail=project.project_code))

    # Bid-only emails for an existing project join the current version rather than
    # starting a new round — the tender document is shared across all bids.
    has_tender = any('tender' in a.file_name.lower() for a in email.attachments)
    existing_ctx = None if has_tender else await repository.get_version_context(project.project_code)
    join_existing = existing_ctx is not None and existing_ctx['version_folder_id'] is not None

    with logfire.span('ingestion.03.resolve_version', project_code=project.project_code):
        if join_existing:
            version = existing_ctx['current_version']
            stages.append(StageResult(stage='03_resolve_version', status='completed', detail=f'version {version:03d} (joining existing)'))
        else:
            version = await repository.next_version(project.project_code)
            stages.append(StageResult(stage='03_resolve_version', status='completed', detail=f'version {version:03d}'))

    with logfire.span('ingestion.04.drive_folders', project_code=project.project_code, version=version):
        if join_existing:
            drive_ctx = DriveContext(
                project_folder_id=existing_ctx['drive_folder_id'],
                version_folder_id=existing_ctx['version_folder_id'],
                version_folder_name=existing_ctx['version_folder_name'] or '',
            )
        else:
            project_folder_id, version_folder_id, version_folder_name = ensure_project_folder(
                settings, project.project_code, project.project_name, version, email.received_at
            )
            drive_ctx = DriveContext(
                project_folder_id=project_folder_id,
                version_folder_id=version_folder_id,
                version_folder_name=version_folder_name,
            )
        stages.append(StageResult(stage='04_drive_folders', status='completed', detail=f'folder {drive_ctx.version_folder_id}'))

    with logfire.span('ingestion.05.drive_upload', project_code=project.project_code):
        drive_files: dict[str, tuple[str, str]] = {}
        for attachment in email.attachments:
            file_id, web_link = upload_attachment(settings, attachment, drive_ctx.version_folder_id)
            drive_files[attachment.file_name] = (file_id, web_link)
        stages.append(StageResult(stage='05_drive_upload', status='completed', detail=f'{len(drive_files)} PDF(s) uploaded'))

    with logfire.span('ingestion.06.persist_postgres', project_code=project.project_code):
        context, files = await repository.persist_email(email, project, version, drive_ctx, drive_files)
        stages.append(StageResult(stage='06_persist_postgres', status='completed', detail=f'project version {context.version}; {len(files)} PDF(s) registered'))

    return IngestionResult(context=context, files=files, stages=stages)
