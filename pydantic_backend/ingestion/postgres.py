"""PostgreSQL persistence; it is the source of truth for email/project/file metadata."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from ..config import Settings
from .models import Attachment, DriveContext, FileType, IncomingEmail, ProjectContext, ProjectSubject, StoredFile

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS employees (
  employee_id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT,
  role TEXT NOT NULL DEFAULT 'REVIEWER' CHECK (role IN ('ADMIN', 'REVIEWER')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS projects (
  project_id UUID PRIMARY KEY,
  project_code TEXT UNIQUE NOT NULL,
  project_name TEXT NOT NULL,
  drive_folder_id TEXT,
  current_version INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  assigned_to UUID REFERENCES employees(employee_id),
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
  email_message_id TEXT,
  email_from TEXT,
  email_subject TEXT,
  email_received_at TIMESTAMPTZ,
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
CREATE TABLE IF NOT EXISTS tender_evaluations (
  evaluation_id UUID PRIMARY KEY,
  file_id UUID NOT NULL UNIQUE REFERENCES file_repository(file_id),
  project_id UUID NOT NULL REFERENCES projects(project_id),
  version INTEGER NOT NULL,
  detection_model TEXT,
  technical_section_title TEXT,
  technical_section_content TEXT,
  technical_status TEXT NOT NULL DEFAULT 'SUGGESTED',
  technical_corrected BOOLEAN NOT NULL DEFAULT false,
  technical_reviewed_by UUID REFERENCES employees(employee_id),
  technical_reviewed_at TIMESTAMPTZ,
  price_section_title TEXT,
  price_section_content TEXT,
  price_status TEXT NOT NULL DEFAULT 'SUGGESTED',
  price_corrected BOOLEAN NOT NULL DEFAULT false,
  price_reviewed_by UUID REFERENCES employees(employee_id),
  price_reviewed_at TIMESTAMPTZ,
  notified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bid_evaluations (
  evaluation_id UUID PRIMARY KEY,
  file_id UUID NOT NULL UNIQUE REFERENCES file_repository(file_id),
  project_id UUID NOT NULL REFERENCES projects(project_id),
  version INTEGER NOT NULL,
  detection_model TEXT,
  technical_section_title TEXT,
  technical_section_content TEXT,
  technical_status TEXT NOT NULL DEFAULT 'SUGGESTED',
  technical_corrected BOOLEAN NOT NULL DEFAULT false,
  technical_reviewed_by UUID REFERENCES employees(employee_id),
  technical_reviewed_at TIMESTAMPTZ,
  price_section_title TEXT,
  price_section_content TEXT,
  price_status TEXT NOT NULL DEFAULT 'SUGGESTED',
  price_corrected BOOLEAN NOT NULL DEFAULT false,
  price_reviewed_by UUID REFERENCES employees(employee_id),
  price_reviewed_at TIMESTAMPTZ,
  notified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
'''

# Additive migrations for databases created before auth/assignment existed — CREATE TABLE
# IF NOT EXISTS above won't retrofit columns onto an already-existing table.
MIGRATION_SQL = '''
ALTER TABLE employees ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'REVIEWER';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES employees(employee_id);
ALTER TABLE file_repository ALTER COLUMN email_message_id DROP NOT NULL;
ALTER TABLE file_repository ALTER COLUMN email_from DROP NOT NULL;
ALTER TABLE file_repository ALTER COLUMN email_subject DROP NOT NULL;
ALTER TABLE file_repository ALTER COLUMN email_received_at DROP NOT NULL;
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
                await cursor.execute(MIGRATION_SQL)
            await connection.commit()

    async def ensure_admin(self, email: str, password_hash: str) -> None:
        """
        Bootstrap the one admin account from ADMIN_EMAIL/ADMIN_PASSWORD. Never overwrites
        an existing password hash for that email (e.g. if an admin already changed
        something out-of-band) — it only ensures the row exists and is role=ADMIN.
        """
        if not email:
            return
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    INSERT INTO employees (employee_id, name, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, 'ADMIN')
                    ON CONFLICT (email) DO UPDATE SET role = 'ADMIN'
                    ''',
                    (str(uuid4()), 'Admin', email, password_hash),
                )
            await connection.commit()

    async def list_projects(self, assigned_to: str | None) -> list[dict]:
        """All projects, or only those assigned to a given employee_id (reviewer scoping)."""
        query = 'SELECT * FROM projects'
        params: tuple = ()
        if assigned_to is not None:
            query += ' WHERE assigned_to = %s'
            params = (assigned_to,)
        query += ' ORDER BY created_at DESC'
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchall()

    async def get_project(self, project_id: str) -> dict | None:
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT * FROM projects WHERE project_id = %s', (project_id,))
                return await cursor.fetchone()

    async def assign_project(self, project_id: str, employee_id: str) -> dict | None:
        """Assign (or reassign) the single reviewer responsible for this project."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'UPDATE projects SET assigned_to = %s, updated_at = now() WHERE project_id = %s RETURNING *',
                    (employee_id, project_id),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return row

    async def create_project(self, project_code: str, project_name: str) -> dict:
        """Create a project directly from the console (no email/Drive folder yet — those are
        created lazily on first file upload, same as the email path)."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                try:
                    await cursor.execute(
                        'INSERT INTO projects (project_id, project_code, project_name) VALUES (%s, %s, %s) RETURNING *',
                        (str(uuid4()), project_code, project_name),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise ValueError(f'A project with code {project_code!r} already exists') from exc
                row = await cursor.fetchone()
            await connection.commit()
        assert row is not None
        return row

    async def set_current_version(self, project_id: str, version: int) -> None:
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'UPDATE projects SET current_version = %s, updated_at = now() WHERE project_id = %s',
                    (version, project_id),
                )
            await connection.commit()

    async def get_version_folder_id(self, project_id: str, version: int) -> str | None:
        """The Drive folder id shared by every file already uploaded at this project/version —
        used to add more files into the current version instead of creating a new Drive folder."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT drive_folder_id FROM file_repository WHERE project_id = %s AND version = %s '
                    'AND drive_folder_id IS NOT NULL LIMIT 1',
                    (project_id, version),
                )
                row = await cursor.fetchone()
                return row['drive_folder_id'] if row else None

    async def insert_direct_file(
        self,
        project_id: str,
        project_code: str,
        project_name: str,
        version: int,
        version_folder_name: str | None,
        file_name: str,
        file_type: str,
        mime_type: str,
        content: bytes,
        drive_file_id: str,
        drive_folder_id: str,
        drive_web_link: str,
    ) -> dict:
        """Insert one file_repository row uploaded directly through the console (no source
        email) — email_* columns stay NULL, distinguishing it from Gmail-ingested files."""
        file_id = str(uuid4())
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''INSERT INTO file_repository (
                        file_id, project_id, project_code, project_name, version,
                        version_folder_name, file_name, file_type, mime_type,
                        file_size_bytes, checksum,
                        drive_file_id, drive_folder_id, drive_web_link,
                        processing_status
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        'RECEIVED'
                    ) RETURNING *''',
                    (
                        file_id, project_id, project_code, project_name, version,
                        version_folder_name, file_name, file_type, mime_type,
                        len(content), hashlib.sha256(content).hexdigest(),
                        drive_file_id, drive_folder_id, drive_web_link,
                    ),
                )
                row = await cursor.fetchone()
            await connection.commit()
        assert row is not None
        return row

    async def update_file_type(self, file_id: str, file_type: str) -> dict | None:
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'UPDATE file_repository SET file_type = %s, updated_at = now() WHERE file_id = %s RETURNING *',
                    (file_type, file_id),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return row

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

    async def get_file(self, file_id: str) -> dict | None:
        """Fetch a single file_repository row (used to re-locate parse artifacts for evaluation review)."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT * FROM file_repository WHERE file_id = %s', (file_id,))
                return await cursor.fetchone()

    async def list_files(self, project_id: str) -> list[dict]:
        """All file_repository rows for a project (every version), newest first. Backs the
        frontend's per-project document list (Workspace bidder/tender lists, Ops table)."""
        async with await AsyncConnection.connect(self.settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT * FROM file_repository WHERE project_id = %s ORDER BY version DESC, file_name',
                    (project_id,),
                )
                return await cursor.fetchall()

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
