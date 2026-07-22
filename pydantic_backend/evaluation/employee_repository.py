"""PostgreSQL access for reviewers (shared across tender and bid evaluation flows)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import bcrypt
from psycopg import AsyncConnection
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from ..config import Settings
from .models import Employee, EmployeeIn, EmployeeUpdate


class EmployeeNotFoundError(Exception):
    pass


class EmployeeInUseError(Exception):
    """Raised when deleting an employee would orphan a project assignment or a recorded review."""


class EmailAlreadyExistsError(Exception):
    pass


@dataclass
class EmployeeRepository:
    settings: Settings

    def _dsn(self) -> str:
        return self.settings.database_url.get_secret_value()

    async def create_employee(self, employee: EmployeeIn) -> Employee:
        employee_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(employee.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    INSERT INTO employees (employee_id, name, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name,
                        password_hash = EXCLUDED.password_hash, role = EXCLUDED.role
                    RETURNING employee_id, name, email, role
                    ''',
                    (employee_id, employee.name, employee.email, password_hash, employee.role.value),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=row['role'])

    async def list_employees(self) -> list[Employee]:
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT employee_id, name, email, role FROM employees ORDER BY name')
                rows = await cursor.fetchall()
        return [Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=row['role']) for row in rows]

    async def update_employee(self, employee_id: str, update: EmployeeUpdate) -> Employee:
        """Patch name/email/role and/or reset the password. Raises EmployeeNotFoundError or
        EmailAlreadyExistsError (if the new email collides with a different employee)."""
        fields: dict[str, object] = {}
        if update.name is not None:
            fields['name'] = update.name
        if update.email is not None:
            fields['email'] = update.email
        if update.role is not None:
            fields['role'] = update.role.value
        if update.password is not None:
            fields['password_hash'] = bcrypt.hashpw(update.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        if not fields:
            existing = await self.get_employee(employee_id)
            if existing is None:
                raise EmployeeNotFoundError(employee_id)
            return existing

        set_clause = ', '.join(f'{column} = %s' for column in fields)
        params = (*fields.values(), employee_id)
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                try:
                    await cursor.execute(
                        f'UPDATE employees SET {set_clause} WHERE employee_id = %s RETURNING employee_id, name, email, role',
                        params,
                    )
                except pg_errors.UniqueViolation as exc:
                    raise EmailAlreadyExistsError(update.email) from exc
                row = await cursor.fetchone()
            if row is None:
                raise EmployeeNotFoundError(employee_id)
            await connection.commit()
        return Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=row['role'])

    async def delete_employee(self, employee_id: str) -> None:
        """Raises EmployeeNotFoundError, or EmployeeInUseError if the employee is still
        assigned to a project or referenced by a recorded review decision."""
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                try:
                    await cursor.execute('DELETE FROM employees WHERE employee_id = %s RETURNING employee_id', (employee_id,))
                except pg_errors.ForeignKeyViolation as exc:
                    raise EmployeeInUseError(employee_id) from exc
                row = await cursor.fetchone()
            if row is None:
                raise EmployeeNotFoundError(employee_id)
            await connection.commit()

    async def get_employee(self, employee_id: str) -> Employee | None:
        async with await AsyncConnection.connect(self._dsn(), row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT employee_id, name, email, role FROM employees WHERE employee_id = %s', (employee_id,))
                row = await cursor.fetchone()
        if row is None:
            return None
        return Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=row['role'])

