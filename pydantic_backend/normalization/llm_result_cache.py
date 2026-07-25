"""
Persisted cache for every LLM-computed normalization result: the aligned technical/price view,
the holistic per-topic score, the detailed cross-topic comparison, and the compliance matrix.
All four are a pure function of the *approved* tender/bid section content for one
project/version, so recomputing (and re-billing) them from scratch on every view is pure
waste. Cached here — generic over `kind`/`topic` rather than one table per result type, since
the get/save/invalidate shape is identical — and invalidated in one place whenever that content
actually changes (see the review endpoint in app.py, which calls `invalidate` after every
approval or correction).
"""
from __future__ import annotations

from psycopg.types.json import Jsonb

from ..config import Settings
from ..db import pool_connection


async def get_cached(settings: Settings, project_id: str, version: int, kind: str, topic: str = '') -> dict | None:
    async with pool_connection(settings) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                'SELECT data FROM llm_result_cache WHERE project_id = %s AND version = %s AND kind = %s AND topic = %s',
                (project_id, version, kind, topic),
            )
            row = await cursor.fetchone()
    return row['data'] if row else None


async def save_cached(settings: Settings, project_id: str, version: int, kind: str, data: dict, topic: str = '') -> None:
    async with pool_connection(settings) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                '''
                INSERT INTO llm_result_cache (project_id, version, kind, topic, data, computed_at)
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (project_id, version, kind, topic) DO UPDATE SET data = EXCLUDED.data, computed_at = now()
                ''',
                (project_id, version, kind, topic, Jsonb(data)),
            )
        await connection.commit()


async def invalidate(settings: Settings, project_id: str, version: int) -> None:
    """Drop every cached kind/topic for this project/version. Approving or correcting any one
    section can affect the aligned view, score, comparison, and matrix alike (compare/matrix
    span both topics), so it's simplest and safest to clear everything for that
    (project_id, version) rather than track exactly which kinds depend on which topic."""
    async with pool_connection(settings) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                'DELETE FROM llm_result_cache WHERE project_id = %s AND version = %s',
                (project_id, version),
            )
        await connection.commit()
