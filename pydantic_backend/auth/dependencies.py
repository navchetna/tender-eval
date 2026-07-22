"""
FastAPI dependencies for HTTP Basic auth. No sessions or tokens: every request carries
`Authorization: Basic <base64(email:password)>` and the password is re-verified against
`employees.password_hash` on every single call (bcrypt.checkpw is fast enough for this
project's request volume, and it avoids any session-store complexity entirely).
"""
from __future__ import annotations

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from ..config import get_settings
from .models import CurrentUser, Role

_security = HTTPBasic()

_UNAUTHORIZED = HTTPException(401, 'Invalid email or password', headers={'WWW-Authenticate': 'Basic'})


async def get_current_user(credentials: HTTPBasicCredentials = Depends(_security)) -> CurrentUser:
    settings = get_settings()
    async with await AsyncConnection.connect(settings.database_url.get_secret_value(), row_factory=dict_row) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                'SELECT employee_id, name, email, password_hash, role FROM employees WHERE email = %s',
                (credentials.username,),
            )
            row = await cursor.fetchone()
    if row is None or not row['password_hash']:
        raise _UNAUTHORIZED
    if not bcrypt.checkpw(credentials.password.encode('utf-8'), row['password_hash'].encode('utf-8')):
        raise _UNAUTHORIZED
    return CurrentUser(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=Role(row['role']))


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != Role.admin:
        raise HTTPException(403, 'Admin privileges required')
    return user
