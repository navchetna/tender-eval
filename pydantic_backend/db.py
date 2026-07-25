"""
Shared async Postgres connection pool.

Every repository used to call `AsyncConnection.connect(dsn)` fresh for every single query —
each one pays a full TCP+TLS+auth round trip to the (remote, Supabase-hosted) database before
the query itself even runs. Worse, `auth/dependencies.py::get_current_user` re-verifies HTTP
Basic credentials this way on *every* authenticated request, so a page that fires a burst of API
calls (dashboard, review queue) pays that connection-setup cost once per call. Pooling keeps a
handful of connections warm so a query only pays for itself.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import Settings

_pools: dict[str, AsyncConnectionPool] = {}


def get_pool(settings: Settings) -> AsyncConnectionPool:
    """One pool per DSN (in practice just one, for the life of the process)."""
    dsn = settings.database_url.get_secret_value()
    pool = _pools.get(dsn)
    if pool is None:
        pool = AsyncConnectionPool(dsn, min_size=2, max_size=10, kwargs={'row_factory': dict_row}, open=False)
        _pools[dsn] = pool
    return pool


@asynccontextmanager
async def pool_connection(settings: Settings) -> AsyncIterator[AsyncConnection]:
    """Drop-in replacement for `await AsyncConnection.connect(dsn, row_factory=dict_row)` —
    same dict-row cursors, but backed by the pool instead of a brand-new connection."""
    pool = get_pool(settings)
    if pool.closed:
        await pool.open()
    async with pool.connection() as connection:
        yield connection


async def start_pool(settings: Settings) -> None:
    """Call once at app startup so the first request doesn't pay the pool's own warm-up cost."""
    pool = get_pool(settings)
    if pool.closed:
        await pool.open(wait=True)


async def stop_pools() -> None:
    for pool in list(_pools.values()):
        await pool.close()
    _pools.clear()
