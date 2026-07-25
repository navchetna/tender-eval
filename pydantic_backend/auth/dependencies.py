"""
FastAPI dependencies for HTTP Basic auth. No sessions or tokens: every request carries
`Authorization: Basic <base64(email:password)>`.

`bcrypt.checkpw` is deliberately slow (~100-300ms) by design, and re-running it — plus a DB
round trip — on every single call was the dominant cost on any page that fires a burst of API
calls (dashboard, review queue): 15 calls in a burst meant 15x that cost, serialized, since
bcrypt.checkpw is a blocking call. A short-lived cache of already-verified (email, password)
pairs skips both the query and the bcrypt check on a hit; a miss still does the full
verification (and populates the cache), so a wrong password is never treated as valid. The
cache is explicitly invalidated on password/role changes and employee deletion (see
`invalidate_user_cache`), with a short TTL as a safety net for any path that doesn't.
"""
from __future__ import annotations

import asyncio
import hashlib
import time

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..config import get_settings
from ..db import pool_connection
from ..evaluation.employee_repository import EmployeeRepository, LlmKeyNotConfiguredError
from ..llm_credentials import LlmCredentials
from .models import CurrentUser, Role

_security = HTTPBasic()

_UNAUTHORIZED = HTTPException(401, 'Invalid email or password', headers={'WWW-Authenticate': 'Basic'})

_CACHE_TTL_SECONDS = 120
_verified_cache: dict[str, tuple[float, CurrentUser]] = {}


def _cache_key(email: str, password: str) -> str:
    # Never keep the raw password around, even in memory.
    return hashlib.sha256(f'{email}\0{password}'.encode('utf-8')).hexdigest()


def invalidate_user_cache(email: str | None = None) -> None:
    """Drop cached verified-credential entries. Called whenever an employee's password, role,
    or existence changes, so a demoted/deleted/repassworded account can't ride a stale cache
    entry until the TTL expires. `email` isn't part of the cache key (the key is a hash of
    email+password, and the caller doesn't know the old password) so on any such change we
    simply clear everything — cheap, and correctness matters more than a few avoidable misses."""
    _verified_cache.clear()


async def get_current_user(credentials: HTTPBasicCredentials = Depends(_security)) -> CurrentUser:
    key = _cache_key(credentials.username, credentials.password)
    now = time.monotonic()
    cached = _verified_cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]

    settings = get_settings()
    async with pool_connection(settings) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                'SELECT employee_id, name, email, password_hash, role FROM employees WHERE email = %s',
                (credentials.username,),
            )
            row = await cursor.fetchone()
    if row is None or not row['password_hash']:
        raise _UNAUTHORIZED
    # bcrypt.checkpw is a blocking C call — run it off the event loop so a cache miss from one
    # request doesn't stall every other concurrent request for its ~100-300ms duration.
    valid = await asyncio.to_thread(bcrypt.checkpw, credentials.password.encode('utf-8'), row['password_hash'].encode('utf-8'))
    if not valid:
        raise _UNAUTHORIZED
    user = CurrentUser(employee_id=str(row['employee_id']), name=row['name'], email=row['email'], role=Role(row['role']))
    _verified_cache[key] = (now + _CACHE_TTL_SECONDS, user)
    return user


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != Role.admin:
        raise HTTPException(403, 'Admin privileges required')
    return user


async def get_llm_credentials(user: CurrentUser = Depends(get_current_user)) -> LlmCredentials:
    """Resolve the caller's own LiteLLM key, so every LLM call they trigger is billed/attributed
    to their account rather than a shared key."""
    settings = get_settings()
    try:
        return await EmployeeRepository(settings).get_llm_credentials(user.employee_id)
    except LlmKeyNotConfiguredError as exc:
        raise HTTPException(403, 'No LiteLLM key assigned to this account — ask an admin to set one') from exc
