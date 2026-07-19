"""PostgreSQL persistence; it is the source of truth for email/project/file metadata."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from ..config import Settings
from .models import Attachment, DriveContext, FileType, IncomingEmail, ProjectContext, ProjectSubject, StoredFile

SCHEMA_SQL = '''
DROP TABLE IF EXISTS file_repository CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
CREATE TABLE IF NOT EXISTS projects (
  project_id UUID PRIMARY KEY,
  project_code TEXT UNIQUE NOT NULL,
  project_name TEXT NOT NULL,
  drive_folder_id TEXT,
  current_version INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS file_repository (
  file_id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(project_id),
  project_code TEXT NOT NULL,
  project_name TEXT NOT NULL,
  version INTEGER NOT NULL,
  version_folder_name TEXT,
  file_name TEXT NOT NULL,
  file_type TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  checksum TEXT NOT NULL,
  drive_file_id TEXT,
  drive_folder_id TEXT,
  drive_web_link TEXT,
  email_message_id TEXT NOT NULL,
  email_from TEXT NOT NULL,
  email_subject TEXT NOT NULL,
  email_received_at TIMESTAMPTZ NOT NULL,
  processing_status TEXT NOT NULL,
  parse_job_id TEXT,
  parse_submitted_at TIMESTAMPTZ,
  parse_completed_at TIMESTAMPTZ,
  parse_error TEXT,
  parse_attempts INTEGER NOT NULL DEFAULT 0,
  drive_parsed_folder_id TEXT,
  drive_images_folder_id TEXT,
  parse_toc TEXT,
  parse_artifacts JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (email_message_id, file_name)
);
'''


def classify(attachment: Attachment) -> FileType:
    name = attachment.file_name.lower()
    return FileType.tender if 'tender' in name else FileType.bid if 'bid' in name else FileType.unknown


@dataclass
class PostgresRepository:
    settings: Settings

    async def initialize(self) -> None:
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(SCHEMA_SQL)
            await connection.commit()

    async def next_version(self, project_code: str) -> int:
        """Return what the next version number will be (1 for new projects, current+1 for existing)."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT current_version FROM projects WHERE project_code = %s', (project_code,))
                row = await cursor.fetchone()
                return (row['current_version'] + 1) if row else 1

    async def is_already_ingested(self, message_id: str) -> bool:
        """Return True if this Gmail message has already been fully ingested."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT 1 FROM file_repository WHERE email_message_id = %s LIMIT 1',
                    (message_id,),
                )
                return await cursor.fetchone() is not None

    async def persist_email(
        self,
        email: IncomingEmail,
        subject: ProjectSubject,
        version: int,
        drive_ctx: DriveContext,
        drive_files: dict[str, tuple[str, str]],
    ) -> tuple[ProjectContext, list[StoredFile]]:
        """Record project + files in one transaction, storing Drive folder/file metadata."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                # Advisory lock prevents concurrent polls racing on the same project code.
                await cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (subject.project_code,))
                await cursor.execute('SELECT project_id, project_name FROM projects WHERE project_code = %s', (subject.project_code,))
                project = await cursor.fetchone()
                if project:
                    project_id = str(project['project_id'])
                    name = project['project_name']
                    await cursor.execute(
                        'UPDATE projects SET current_version = %s, drive_folder_id = %s, updated_at = now() WHERE project_id = %s',
                        (version, drive_ctx.project_folder_id, project_id),
                    )
                else:
                    project_id = str(uuid4())
                    name = subject.project_name
                    await cursor.execute(
                        'INSERT INTO projects (project_id, project_code, project_name, current_version, drive_folder_id) VALUES (%s, %s, %s, %s, %s)',
                        (project_id, subject.project_code, name, version, drive_ctx.project_folder_id),
                    )
                context = ProjectContext(
                    project_id=project_id,
                    project_code=subject.project_code,
                    project_name=name,
                    version=version,
                    email_message_id=email.message_id,
                    drive_project_folder_id=drive_ctx.project_folder_id,
                    drive_version_folder_id=drive_ctx.version_folder_id,
                    drive_version_folder_name=drive_ctx.version_folder_name,
                )
                files: list[StoredFile] = []
                for attachment in email.attachments:
                    file_id = str(uuid4())
                    file_type = classify(attachment)
                    drive_file_id, drive_web_link = drive_files.get(attachment.file_name, ('', ''))
                    await cursor.execute(
                        '''INSERT INTO file_repository (
                            file_id, project_id, project_code, project_name, version,
                            version_folder_name, file_name, file_type, mime_type,
                            file_size_bytes, checksum,
                            drive_file_id, drive_folder_id, drive_web_link,
                            email_message_id, email_from, email_subject, email_received_at,
                            processing_status
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            'RECEIVED'
                        ) ON CONFLICT (email_message_id, file_name) DO NOTHING''',
                        (
                            file_id, project_id, subject.project_code, name, version,
                            drive_ctx.version_folder_name, attachment.file_name, file_type.value, attachment.mime_type,
                            len(attachment.content), hashlib.sha256(attachment.content).hexdigest(),
                            drive_file_id, drive_ctx.version_folder_id, drive_web_link,
                            email.message_id, email.sender, email.subject, email.received_at,
                        ),
                    )
                    files.append(StoredFile(
                        file_id=file_id, file_name=attachment.file_name, file_type=file_type,
                        processing_status='RECEIVED', drive_file_id=drive_file_id, drive_web_link=drive_web_link,
                    ))
            await connection.commit()
            return context, files
