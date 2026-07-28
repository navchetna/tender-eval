"""PostgreSQL persistence; it is the source of truth for email/project/file metadata."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

import psycopg

from ..config import Settings
from ..db import pool_connection
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
-- Every LLM-computed normalization result (aligned technical/price view, holistic score,
-- detailed comparison, compliance matrix) is a pure function of the *approved* tender/bid
-- section content for one project/version, yet was previously recomputed — and re-billed —
-- from scratch on every single view. Cached here, keyed by (project_id, version, kind, topic),
-- and invalidated in one place whenever that content actually changes (see
-- EvaluationRepository.approve/correct in app.py, which clear every row for their project/version).
CREATE TABLE IF NOT EXISTS llm_result_cache (
  project_id UUID NOT NULL REFERENCES projects(project_id),
  version INTEGER NOT NULL,
  kind TEXT NOT NULL,              -- 'view' | 'score' | 'compare' | 'matrix'
  topic TEXT NOT NULL DEFAULT '',  -- 'technical' | 'price' | '' (compare/matrix span both)
  data JSONB NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, version, kind, topic)
);
'''

# Additive migrations for databases created before auth/assignment existed — CREATE TABLE
# IF NOT EXISTS above won't retrofit columns onto an already-existing table.
MIGRATION_SQL = '''
ALTER TABLE employees ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'REVIEWER';
-- Per-employee LiteLLM keys are gone: every call now goes through one local LiteLLM proxy
-- with a shared master key (see llm_credentials.py), so this column has no reader left.
ALTER TABLE employees DROP COLUMN IF EXISTS litellm_key_encrypted;
ALTER TABLE file_repository ADD COLUMN IF NOT EXISTS detection_error TEXT;
ALTER TABLE tender_evaluations ADD COLUMN IF NOT EXISTS technical_ai_title TEXT;
ALTER TABLE tender_evaluations ADD COLUMN IF NOT EXISTS technical_ai_content TEXT;
ALTER TABLE tender_evaluations ADD COLUMN IF NOT EXISTS price_ai_title TEXT;
ALTER TABLE tender_evaluations ADD COLUMN IF NOT EXISTS price_ai_content TEXT;
ALTER TABLE bid_evaluations ADD COLUMN IF NOT EXISTS technical_ai_title TEXT;
ALTER TABLE bid_evaluations ADD COLUMN IF NOT EXISTS technical_ai_content TEXT;
ALTER TABLE bid_evaluations ADD COLUMN IF NOT EXISTS price_ai_title TEXT;
ALTER TABLE bid_evaluations ADD COLUMN IF NOT EXISTS price_ai_content TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES employees(employee_id);
ALTER TABLE file_repository ALTER COLUMN email_message_id DROP NOT NULL;
ALTER TABLE file_repository ALTER COLUMN email_from DROP NOT NULL;
ALTER TABLE file_repository ALTER COLUMN email_subject DROP NOT NULL;
ALTER TABLE file_repository ALTER COLUMN email_received_at DROP NOT NULL;
-- Superseded by llm_result_cache above (same idea, generalized to every LLM-computed result).
DROP TABLE IF EXISTS compliance_matrix_cache;
'''


def classify(attachment: Attachment) -> FileType:
    name = attachment.file_name.lower()
    return FileType.tender if 'tender' in name else FileType.bid if 'bid' in name else FileType.unknown


@dataclass
class PostgresRepository:
    settings: Settings

    async def initialize(self) -> None:
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(SCHEMA_SQL)
                await cursor.execute(MIGRATION_SQL)
            await connection.commit()

    async def ensure_admin(self, email: str, password_hash: str) -> None:
        """
        Bootstrap the one admin account from ADMIN_EMAIL/ADMIN_PASSWORD. Never overwrites an
        existing password hash for that email (e.g. if the admin already changed it
        out-of-band) — on conflict it only ensures role=ADMIN.
        """
        if not email:
            return
        async with pool_connection(self.settings) as connection:
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
        """All projects, or only those assigned to a given employee_id (reviewer scoping).

        `evaluation_completed` is true once a final cross-topic comparison has been generated
        for the project's *current* version (llm_result_cache, kind='compare') — it goes back
        to false the moment a correction invalidates that cache entry, and naturally resets
        when a new version starts, since the subquery is pinned to current_version.
        """
        query = '''
            SELECT p.*, EXISTS (
                SELECT 1 FROM llm_result_cache c
                WHERE c.project_id = p.project_id AND c.version = p.current_version AND c.kind = 'compare'
            ) AS evaluation_completed
            FROM projects p
        '''
        params: tuple = ()
        if assigned_to is not None:
            query += ' WHERE p.assigned_to = %s'
            params = (assigned_to,)
        query += ' ORDER BY p.created_at DESC'
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchall()

    async def get_project(self, project_id: str) -> dict | None:
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT * FROM projects WHERE project_id = %s', (project_id,))
                return await cursor.fetchone()

    async def delete_project(self, project_id: str) -> bool:
        """Permanently remove a project and everything scoped to it (every version's files,
        tender/bid evaluations, cached LLM results). No FK is ON DELETE CASCADE, so the
        dependents are deleted first, in one transaction. Returns False if the project
        didn't exist."""
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('DELETE FROM llm_result_cache WHERE project_id = %s', (project_id,))
                await cursor.execute('DELETE FROM tender_evaluations WHERE project_id = %s', (project_id,))
                await cursor.execute('DELETE FROM bid_evaluations WHERE project_id = %s', (project_id,))
                await cursor.execute('DELETE FROM file_repository WHERE project_id = %s', (project_id,))
                await cursor.execute('DELETE FROM projects WHERE project_id = %s RETURNING project_id', (project_id,))
                deleted = await cursor.fetchone()
            await connection.commit()
        return deleted is not None

    async def assign_project(self, project_id: str, employee_id: str) -> dict | None:
        """Assign (or reassign) the single reviewer responsible for this project."""
        async with pool_connection(self.settings) as connection:
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
        async with pool_connection(self.settings) as connection:
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
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'UPDATE projects SET current_version = %s, updated_at = now() WHERE project_id = %s',
                    (version, project_id),
                )
            await connection.commit()

    async def get_version_folder_id(self, project_id: str, version: int) -> str | None:
        """The Drive folder id shared by every file already uploaded at this project/version —
        used to add more files into the current version instead of creating a new Drive folder."""
        async with pool_connection(self.settings) as connection:
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
        async with pool_connection(self.settings) as connection:
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
        """
        Reclassifying a file (e.g. TENDER -> BID) must also drop any evaluation row it already
        has under its *old* classification — otherwise that row is orphaned (references a file
        that's no longer a tender/bid), and worse, claim_pending_files() for the *new* type sees
        a PARSED file with no evaluation row yet in the new type's table and detects it fresh,
        producing a second, duplicate evaluation for the same file (and an inflated pending
        count in the review queue) alongside the stale original.
        """
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'UPDATE file_repository SET file_type = %s, updated_at = now() WHERE file_id = %s RETURNING *',
                    (file_type, file_id),
                )
                row = await cursor.fetchone()
                if file_type != 'TENDER':
                    await cursor.execute('DELETE FROM tender_evaluations WHERE file_id = %s', (file_id,))
                if file_type != 'BID':
                    await cursor.execute('DELETE FROM bid_evaluations WHERE file_id = %s', (file_id,))
            await connection.commit()
        return row

    async def next_version(self, project_code: str) -> int:
        """Return what the next version number will be (1 for new projects, current+1 for existing)."""
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT current_version FROM projects WHERE project_code = %s', (project_code,))
                row = await cursor.fetchone()
                return (row['current_version'] + 1) if row else 1

    async def is_already_ingested(self, message_id: str) -> bool:
        """Return True if this Gmail message has already been fully ingested."""
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT 1 FROM file_repository WHERE email_message_id = %s LIMIT 1',
                    (message_id,),
                )
                return await cursor.fetchone() is not None

    async def get_file(self, file_id: str) -> dict | None:
        """Fetch a single file_repository row (used to re-locate parse artifacts for evaluation review)."""
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT * FROM file_repository WHERE file_id = %s', (file_id,))
                return await cursor.fetchone()

    async def list_files(self, project_id: str) -> list[dict]:
        """All file_repository rows for a project (every version), newest first. Backs the
        frontend's per-project document list (Workspace bidder/tender lists, Ops table)."""
        async with pool_connection(self.settings) as connection:
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
        async with pool_connection(self.settings) as connection:
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
