"""PostgreSQL access for the evaluation stage: claim tender files, employees, review lifecycle."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..config import Settings
from .models import Employee, EmployeeIn, EvaluationRecord, PendingTenderFile, SectionSuggestion, Topic


@dataclass
class EvaluationRepository:
    settings: Settings

    def _dsn(self) -> str:
        return self.settings.database_url.get_secret_value()

    async def claim_pending_tender_files(self, limit: int) -> list[PendingTenderFile]:
        """
        PARSED tender documents (file_type='tender') that don't have an evaluation row yet.

        No FOR UPDATE SKIP LOCKED trickery needed here: the INSERT in create_evaluation
        uses the file_id UNIQUE constraint on tender_evaluations as the concurrency guard.
        """
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    SELECT f.file_id, f.project_id, f.version, f.file_name, f.parse_toc, f.parse_artifacts
                    FROM file_repository f
                    LEFT JOIN tender_evaluations e ON e.file_id = f.file_id
                    WHERE f.file_type = 'TENDER'
                      AND f.processing_status = 'PARSED'
                      AND e.evaluation_id IS NULL
                    ORDER BY f.created_at
                    LIMIT %s
                    ''',
                    (limit,),
                )
                rows = await cursor.fetchall()
        return [PendingTenderFile(**{**row, 'file_id': str(row['file_id']), 'project_id': str(row['project_id'])}) for row in rows]

    async def create_evaluation(
        self,
        file: PendingTenderFile,
        technical: SectionSuggestion,
        price: SectionSuggestion,
        model: str,
    ) -> str | None:
        """Insert the AI-suggested evaluation row; returns the new evaluation_id, or None if one already exists."""
        evaluation_id = str(uuid.uuid4())
        async with await AsyncConnection.connect(self._dsn()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    INSERT INTO tender_evaluations (
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
                    'UPDATE tender_evaluations SET notified_at = now(), updated_at = now() WHERE evaluation_id = %s',
                    (evaluation_id,),
                )
            await connection.commit()

    async def get_evaluation(self, evaluation_id: str) -> EvaluationRecord | None:
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT * FROM tender_evaluations WHERE evaluation_id = %s', (evaluation_id,))
                row = await cursor.fetchone()
        if row is None:
            return None
        return _to_record(row)

    async def list_pending_review(self) -> list[EvaluationRecord]:
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT * FROM tender_evaluations WHERE technical_status = 'SUGGESTED' OR price_status = 'SUGGESTED' ORDER BY created_at"
                )
                rows = await cursor.fetchall()
        return [_to_record(row) for row in rows]

    async def approve(self, evaluation_id: str, topic: Topic, employee_id: str) -> None:
        column_prefix = topic.value
        async with await AsyncConnection.connect(self._dsn()) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f'''
                    UPDATE tender_evaluations
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
                    UPDATE tender_evaluations
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

    # --- Employees ---------------------------------------------------------------

    async def create_employee(self, employee: EmployeeIn) -> Employee:
        employee_id = str(uuid.uuid4())
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    INSERT INTO employees (employee_id, name, email) VALUES (%s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
                    RETURNING employee_id, name, email
                    ''',
                    (employee_id, employee.name, employee.email),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'])

    async def list_employees(self) -> list[Employee]:
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT employee_id, name, email FROM employees ORDER BY name')
                rows = await cursor.fetchall()
        return [Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email']) for row in rows]


def _to_record(row: dict) -> EvaluationRecord:
    return EvaluationRecord(
        evaluation_id=str(row['evaluation_id']),
        file_id=str(row['file_id']),
        project_id=str(row['project_id']),
        version=row['version'],
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
