"""PostgreSQL access for the parsing stage: claim pending files and record parse state."""
from __future__ import annotations

from dataclasses import dataclass

from psycopg.types.json import Jsonb

from ..config import Settings
from ..db import pool_connection
from .models import ParseArtifacts, PendingFile


@dataclass
class ParsingRepository:
    settings: Settings

    async def claim_pending_files(self, limit: int) -> list[PendingFile]:
        """
        Atomically claim up to `limit` files that are ready to parse and mark them PARSING.

        Uses FOR UPDATE SKIP LOCKED so multiple workers can run concurrently without
        picking the same rows. Only RECEIVED (or retryable PARSE_FAILED under the attempt
        cap) files with a Drive file id are eligible.
        """
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    WITH claimed AS (
                        SELECT file_id
                        FROM file_repository
                        WHERE drive_file_id IS NOT NULL
                          AND drive_file_id <> ''
                          AND (
                                processing_status = 'RECEIVED'
                                OR (processing_status = 'PARSE_FAILED' AND parse_attempts < %s)
                          )
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE file_repository f
                    SET processing_status = 'PARSING',
                        parse_submitted_at = now(),
                        parse_attempts = f.parse_attempts + 1,
                        updated_at = now()
                    FROM claimed
                    WHERE f.file_id = claimed.file_id
                    RETURNING f.file_id, f.file_name, f.drive_file_id, f.mime_type,
                              f.drive_folder_id AS version_folder_id, f.parse_attempts
                    ''',
                    (self.settings.parse_max_attempts, limit),
                )
                rows = await cursor.fetchall()
            await connection.commit()
        return [PendingFile(**{**row, 'file_id': str(row['file_id'])}) for row in rows]

    async def claim_file_for_retry(self, file_id: str) -> PendingFile | None:
        """
        Reclaim one specific PARSE_FAILED file for a manual retry, bypassing the
        `parse_attempts < parse_max_attempts` cap enforced by `claim_pending_files` — that
        cap only exists to stop the unattended worker from retrying a dead file forever, not
        to block an explicit human retry. Returns None if the file isn't currently failed.
        """
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    UPDATE file_repository
                    SET processing_status = 'PARSING',
                        parse_submitted_at = now(),
                        parse_attempts = parse_attempts + 1,
                        updated_at = now()
                    WHERE file_id = %s AND processing_status = 'PARSE_FAILED'
                    RETURNING file_id, file_name, drive_file_id, mime_type,
                              drive_folder_id AS version_folder_id, parse_attempts
                    ''',
                    (file_id,),
                )
                row = await cursor.fetchone()
            await connection.commit()
        if row is None:
            return None
        return PendingFile(**{**row, 'file_id': str(row['file_id'])})

    async def set_job_id(self, file_id: str, job_id: str) -> None:
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    'UPDATE file_repository SET parse_job_id = %s, updated_at = now() WHERE file_id = %s',
                    (job_id, file_id),
                )
            await connection.commit()

    async def mark_parsed(self, file_id: str, artifacts: ParseArtifacts) -> None:
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    UPDATE file_repository
                    SET processing_status = 'PARSED',
                        parse_completed_at = now(),
                        parse_error = NULL,
                        drive_parsed_folder_id = %s,
                        drive_images_folder_id = %s,
                        parse_toc = %s,
                        parse_artifacts = %s,
                        updated_at = now()
                    WHERE file_id = %s
                    ''',
                    (
                        artifacts.parsed_folder_id,
                        artifacts.images_folder_id,
                        artifacts.toc_content,
                        Jsonb(artifacts.model_dump()),
                        file_id,
                    ),
                )
            await connection.commit()

    async def mark_failed(self, file_id: str, error: str) -> None:
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    UPDATE file_repository
                    SET processing_status = 'PARSE_FAILED',
                        parse_error = %s,
                        updated_at = now()
                    WHERE file_id = %s
                    ''',
                    (error[:2000], file_id),
                )
            await connection.commit()
