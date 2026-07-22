"""PostgreSQL access for the section-evaluation stage (works for both tender and bid documents)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from ..config import Settings
from .models import DocType, EvaluationRecord, PendingFile, SectionSuggestion, Topic

_TABLE_BY_DOC_TYPE = {
    DocType.tender: 'tender_evaluations',
    DocType.bid: 'bid_evaluations',
}


@dataclass
class EvaluationRepository:
    """
    Generic repository parameterised by document type (tender/bid). Both `tender_evaluations`
    and `bid_evaluations` have an identical shape, so the same code drives both flows.
    `doc_type` only ever comes from trusted server-side call sites (never raw user input),
    and is restricted to the two DocType enum members, so interpolating `self._table` is safe.
    """

    settings: Settings
    doc_type: DocType

    @property
    def _table(self) -> str:
        return _TABLE_BY_DOC_TYPE[self.doc_type]

    def _dsn(self) -> str:
        return self.settings.database_url.get_secret_value()

    async def claim_pending_files(self, limit: int) -> list[PendingFile]:
        """PARSED file_repository rows of this doc_type that don't have an evaluation yet."""
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    SELECT f.file_id, f.project_id, f.version, f.file_name, f.parse_toc, f.parse_artifacts
                    FROM file_repository f
                    LEFT JOIN {self._table} e ON e.file_id = f.file_id
                    WHERE f.file_type = %s
                      AND f.processing_status = 'PARSED'
                      AND e.evaluation_id IS NULL
                    ORDER BY f.created_at
                    LIMIT %s
                    ''',
                    (self.doc_type.value, limit),
                )
                rows = await cursor.fetchall()
        return [PendingFile(**{**row, 'file_id': str(row['file_id']), 'project_id': str(row['project_id'])}) for row in rows]

    async def create_evaluation(
        self,
        file: PendingFile,
        technical: SectionSuggestion,
        price: SectionSuggestion,
        model: str,
    ) -> str | None:
        """Insert the AI-suggested evaluation row; returns the new evaluation_id, or None if one already exists."""
        evaluation_id = str(uuid.uuid4())
        async with await AsyncConnection.connect(self._dsn()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    INSERT INTO {self._table} (
                        evaluation_id, file_id, project_id, version, detection_model,
                        technical_section_title, technical_section_content,
                        price_section_title, price_section_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_id) DO NOTHING
                    ''',
                    (
                        evaluation_id, file.file_id, file.project_id, file.version, model,
                        technical.heading, technical.content,
                        price.heading, price.content,
                    ),
                )
                inserted = cursor.rowcount == 1
            await connection.commit()
        return evaluation_id if inserted else None

    async def mark_notified(self, evaluation_id: str) -> None:
        async with await AsyncConnection.connect(self._dsn()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'UPDATE {self._table} SET notified_at = now(), updated_at = now() WHERE evaluation_id = %s',
                    (evaluation_id,),
                )
            await connection.commit()

    async def get_evaluation(self, evaluation_id: str) -> EvaluationRecord | None:
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    SELECT e.*, f.file_name
                    FROM {self._table} e
                    JOIN file_repository f ON f.file_id = e.file_id
                    WHERE e.evaluation_id = %s
                    ''',
                    (evaluation_id,),
                )
                row = await cursor.fetchone()
        if row is None:
            return None
        return _to_record(row)

    async def list_pending_review(self, employee_id: str | None = None) -> list[EvaluationRecord]:
        """
        Evaluations still awaiting a technical/price decision. When `employee_id` is given,
        only evaluations for projects assigned to that reviewer are returned (per-project
        task delegation); `None` (admin) returns everything, same as before delegation existed.
        """
        query = f'''
            SELECT e.*, f.file_name
            FROM {self._table} e
            JOIN file_repository f ON f.file_id = e.file_id
        '''
        params: tuple = ()
        if employee_id is not None:
            query += ' JOIN projects p ON p.project_id = e.project_id AND p.assigned_to = %s'
            params = (employee_id,)
        query += " WHERE e.technical_status = 'SUGGESTED' OR e.price_status = 'SUGGESTED' ORDER BY e.created_at"
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
        return [_to_record(row) for row in rows]

    async def list_by_project_version(self, project_id: str, version: int) -> list[EvaluationRecord]:
        """
        All evaluations of this doc_type for a given project/version.

        For tender_evaluations this normally returns 0 or 1 row; for bid_evaluations it
        returns one row per bidder's file. Used to assemble the normalized comparison view
        on demand — nothing new is persisted for this.
        """
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    SELECT e.*, f.file_name
                    FROM {self._table} e
                    JOIN file_repository f ON f.file_id = e.file_id
                    WHERE e.project_id = %s AND e.version = %s
                    ORDER BY f.file_name
                    ''',
                    (project_id, version),
                )
                rows = await cursor.fetchall()
        return [_to_record(row) for row in rows]

    async def approve(self, evaluation_id: str, topic: Topic, employee_id: str) -> None:
        column_prefix = topic.value
        async with await AsyncConnection.connect(self._dsn()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    UPDATE {self._table}
                    SET {column_prefix}_status = 'APPROVED',
                        {column_prefix}_reviewed_by = %s,
                        {column_prefix}_reviewed_at = now(),
                        updated_at = now()
                    WHERE evaluation_id = %s
                    ''',
                    (employee_id, evaluation_id),
                )
            await connection.commit()

    async def correct(
        self, evaluation_id: str, topic: Topic, employee_id: str, heading: str, content: str | None
    ) -> None:
        """Human picked a different TOC heading as the correct section; store it and mark approved+corrected."""
        column_prefix = topic.value
        async with await AsyncConnection.connect(self._dsn()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    UPDATE {self._table}
                    SET {column_prefix}_section_title = %s,
                        {column_prefix}_section_content = %s,
                        {column_prefix}_status = 'APPROVED',
                        {column_prefix}_corrected = true,
                        {column_prefix}_reviewed_by = %s,
                        {column_prefix}_reviewed_at = now(),
                        updated_at = now()
                    WHERE evaluation_id = %s
                    ''',
                    (heading, content, employee_id, evaluation_id),
                )
            await connection.commit()


def tender_repository(settings: Settings) -> EvaluationRepository:
    return EvaluationRepository(settings, DocType.tender)


def bid_repository(settings: Settings) -> EvaluationRepository:
    return EvaluationRepository(settings, DocType.bid)


def _to_record(row: dict) -> EvaluationRecord:
    return EvaluationRecord(
        evaluation_id=str(row['evaluation_id']),
        file_id=str(row['file_id']),
        project_id=str(row['project_id']),
        version=row['version'],
        file_name=row.get('file_name'),
        detection_model=row['detection_model'],
        technical_section_title=row['technical_section_title'],
        technical_section_content=row['technical_section_content'],
        technical_status=row['technical_status'],
        technical_corrected=row['technical_corrected'],
        technical_reviewed_by=str(row['technical_reviewed_by']) if row['technical_reviewed_by'] else None,
        technical_reviewed_at=row['technical_reviewed_at'],
        price_section_title=row['price_section_title'],
        price_section_content=row['price_section_content'],
        price_status=row['price_status'],
        price_corrected=row['price_corrected'],
        price_reviewed_by=str(row['price_reviewed_by']) if row['price_reviewed_by'] else None,
        price_reviewed_at=row['price_reviewed_at'],
        notified_at=row['notified_at'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )

