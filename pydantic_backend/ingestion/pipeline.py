import re

import logfire

from ..config import Settings
from .drive import ensure_project_folder, upload_attachment
from .models import DriveContext, IncomingEmail, IngestionResult, ProjectSubject, StageResult
from .postgres import PostgresRepository

SUBJECT_PATTERN = re.compile(r'^\s*(?P<code>[A-Za-z0-9][A-Za-z0-9_-]*)\s*:\s*(?P<name>.+?)\s*$')


class AlreadyIngestedError(Exception):
    pass


def parse_subject(subject: str) -> ProjectSubject:
    match = SUBJECT_PATTERN.match(subject)
    if not match:
        raise ValueError('Malformed subject; expected `<Project Code>: <Project Name>`')
    return ProjectSubject(project_code=match.group('code'), project_name=match.group('name'))


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
        stages.append(StageResult(stage='01_validate_email', status='completed'))

    with logfire.span('ingestion.02.parse_subject'):
        project = parse_subject(email.subject)
        stages.append(StageResult(stage='02_parse_subject', status='completed', detail=project.project_code))

    with logfire.span('ingestion.03.resolve_version', project_code=project.project_code):
        version = await repository.next_version(project.project_code)
        stages.append(StageResult(stage='03_resolve_version', status='completed', detail=f'version {version:03d}'))

    with logfire.span('ingestion.04.drive_folders', project_code=project.project_code, version=version):
        project_folder_id, version_folder_id, version_folder_name = ensure_project_folder(
            settings, project.project_code, project.project_name, version, email.received_at
        )
        drive_ctx = DriveContext(
            project_folder_id=project_folder_id,
            version_folder_id=version_folder_id,
            version_folder_name=version_folder_name,
        )
        stages.append(StageResult(stage='04_drive_folders', status='completed', detail=f'folder {version_folder_id}'))

    with logfire.span('ingestion.05.drive_upload', project_code=project.project_code):
        drive_files: dict[str, tuple[str, str]] = {}
        for attachment in email.attachments:
            file_id, web_link = upload_attachment(settings, attachment, version_folder_id)
            drive_files[attachment.file_name] = (file_id, web_link)
        stages.append(StageResult(stage='05_drive_upload', status='completed', detail=f'{len(drive_files)} PDF(s) uploaded'))

    with logfire.span('ingestion.06.persist_postgres', project_code=project.project_code):
        context, files = await repository.persist_email(email, project, version, drive_ctx, drive_files)
        stages.append(StageResult(stage='06_persist_postgres', status='completed', detail=f'project version {context.version}; {len(files)} PDF(s) registered'))

    return IngestionResult(context=context, files=files, stages=stages)
