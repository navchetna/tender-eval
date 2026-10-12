"""
Which model does the reasoning ("quality") tier — compliance matrix, section scoring, the final
cross-bid comparison: Claude, or the same on-device Qwen that already does the fast tier.

An admin toggles it from the Operations page; the choice is stored in `app_settings` (so it
survives restarts and needs no config edit) and read on every quality-tier request:

  - 'auto'   (default) Claude when it's configured, otherwise the on-device model — so an install
             without a Claude subscription works out of the box.
  - 'claude' always Claude (calls fail with a clear message if it isn't configured).
  - 'local'  always the on-device model, even when Claude is configured (e.g. fully offline,
             or to avoid cloud cost).
"""
from __future__ import annotations

from typing import Literal

import psycopg
from pydantic import BaseModel

from .config import Settings
from .db import pool_connection

ReasoningChoice = Literal['auto', 'claude', 'local']
_KEY = 'reasoning_model'

# The choice is read on every quality-tier request; a process-local copy avoids a DB round trip
# each time. This process is the only writer (set_choice refreshes it), so it can't go stale.
_cached: ReasoningChoice | None = None


class ReasoningModelState(BaseModel):
    choice: ReasoningChoice
    effective: Literal['claude', 'local']
    claude_configured: bool
    claude_model: str
    local_model: str


def claude_configured(settings: Settings) -> bool:
    if settings.model_runtime == 'litellm':
        return True  # the LiteLLM proxy owns the Claude credentials; nothing to check here
    return bool(settings.anthropic_api_key.get_secret_value() or settings.quality_llm_base_url)


def claude_model_name(settings: Settings) -> str:
    if settings.model_runtime == 'litellm':
        return settings.litellm_quality_model
    return settings.quality_llm_model if settings.quality_llm_base_url else settings.anthropic_quality_model


def local_model_name(settings: Settings) -> str:
    return settings.local_fast_model_repo if settings.model_runtime == 'inprocess' else settings.litellm_fast_model


def resolve(settings: Settings, choice: ReasoningChoice) -> Literal['claude', 'local']:
    if choice == 'auto':
        return 'claude' if claude_configured(settings) else 'local'
    return choice


async def get_choice(settings: Settings) -> ReasoningChoice:
    global _cached
    if _cached is None:
        try:
            async with pool_connection(settings) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute('SELECT value FROM app_settings WHERE key = %s', (_KEY,))
                    row = await cursor.fetchone()
        except psycopg.errors.UndefinedTable:
            # A database created before app_settings existed (POST /setup/database adds it).
            return 'auto'
        value = row['value'] if row else 'auto'
        _cached = value if value in ('auto', 'claude', 'local') else 'auto'
    return _cached


async def set_choice(settings: Settings, choice: ReasoningChoice) -> None:
    global _cached
    async with pool_connection(settings) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                '''
                INSERT INTO app_settings (key, value, updated_at) VALUES (%s, %s, now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                ''',
                (_KEY, choice),
            )
            # Every cached matrix/score/comparison was produced by the previous model — drop them
            # so the next view is recomputed by the newly selected one.
            await cursor.execute('DELETE FROM llm_result_cache')
        await connection.commit()
    _cached = choice


async def state(settings: Settings) -> ReasoningModelState:
    choice = await get_choice(settings)
    return ReasoningModelState(
        choice=choice,
        effective=resolve(settings, choice),
        claude_configured=claude_configured(settings),
        claude_model=claude_model_name(settings),
        local_model=local_model_name(settings),
    )
