"""Background worker that periodically parses pending PDFs."""
from __future__ import annotations

import asyncio

import logfire

from ..config import Settings
from .service import process_pending


async def run_worker(settings: Settings, stop: asyncio.Event) -> None:
    """Loop until `stop` is set, processing pending files each interval."""
    logfire.info('parsing worker started', interval=settings.parse_worker_interval_seconds)
    while not stop.is_set():
        try:
            outcomes = await process_pending(settings)
            if outcomes:
                logfire.info('parsing worker batch complete', processed=len(outcomes))
        except Exception:  # noqa: BLE001 — keep the loop alive across transient failures
            logfire.exception('parsing worker iteration failed')
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.parse_worker_interval_seconds)
        except asyncio.TimeoutError:
            pass
    logfire.info('parsing worker stopped')
