"""PostgreSQL access for reviewers (shared across tender and bid evaluation flows)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import bcrypt
from psycopg import errors as pg_errors

from ..config import Settings
from ..db import pool_connection
from ..llm_credentials import LlmCredentials, decrypt_key, encrypt_key
from .models import Employee, EmployeeIn, EmployeeUpdate


class EmployeeNotFoundError(Exception):
    pass


class EmployeeInUseError(Exception):
    """Raised when deleting an employee would orphan a project assignment or a recorded review."""


class EmailAlreadyExistsError(Exception):
    pass


class LlmKeyNotConfiguredError(Exception):
    """Raised when an employee has no LiteLLM key assigned yet — an admin must set one."""


@dataclass
class EmployeeRepository:
    settings: Settings

    async def create_employee(self, employee: EmployeeIn) -> Employee:
        employee_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(employee.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        litellm_key_encrypted = encrypt_key(employee.litellm_key, self.settings)
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    '''
                    INSERT INTO employees (employee_id, name, email, password_hash, role, litellm_key_encrypted)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name,
                        password_hash = EXCLUDED.password_hash, role = EXCLUDED.role,
                        litellm_key_encrypted = EXCLUDED.litellm_key_encrypted
                    RETURNING employee_id, name, email, role
                    ''',
                    (employee_id, employee.name, employee.email, password_hash, employee.role.value, litellm_key_encrypted),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=row['role'])

    async def list_employees(self) -> list[Employee]:
        async with pool_connection(self.settings) as connection:
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
        if update.litellm_key is not None:
            fields['litellm_key_encrypted'] = encrypt_key(update.litellm_key, self.settings)
        if not fields:
            existing = await self.get_employee(employee_id)
            if existing is None:
                raise EmployeeNotFoundError(employee_id)
            return existing

        set_clause = ', '.join(f'{column} = %s' for column in fields)
        params = (*fields.values(), employee_id)
        async with pool_connection(self.settings) as connection:
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
        async with pool_connection(self.settings) as connection:
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
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT employee_id, name, email, role FROM employees WHERE employee_id = %s', (employee_id,))
                row = await cursor.fetchone()
        if row is None:
            return None
        return Employee(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=row['role'])

    async def get_llm_credentials(self, employee_id: str) -> LlmCredentials:
        """Resolve this employee's own LiteLLM key for use on their behalf. Raises
        LlmKeyNotConfiguredError if no key has been assigned yet."""
        async with pool_connection(self.settings) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT litellm_key_encrypted FROM employees WHERE employee_id = %s', (employee_id,))
                row = await cursor.fetchone()
        if row is None or not row['litellm_key_encrypted']:
            raise LlmKeyNotConfiguredError(employee_id)
        return LlmCredentials(
            api_key=decrypt_key(row['litellm_key_encrypted'], self.settings),
            base_url=self.settings.litellm_base_url,
            model=self.settings.litellm_model,
            verify_tls=self.settings.litellm_verify_tls,
        )

