"""
Background pipeline worker: periodically parses pending PDFs, then runs technical/price
section-detection for newly-parsed tender and bid files. This is what lets uploaded documents
progress on their own (RECEIVED -> PARSED -> SUGGESTED evaluations) without an admin manually
clicking "process pending" after every upload.
"""
from __future__ import annotations

import asyncio

import logfire

from ..config import Settings
from ..evaluation.repository import bid_repository, tender_repository
from ..evaluation.service import process_pending as process_pending_evaluations
from ..llm_credentials import fast_llm_credentials
from .service import process_pending as process_pending_parses


async def _run_stage(name: str, coro) -> list:
    """Run one pipeline stage; a failure here must never stop the other stages or the loop
    itself (matches the per-file/per-batch exception-swallowing already used in
    evaluation/service.py and the previous version of this worker)."""
    try:
        outcome = await coro
        if outcome:
            logfire.info(f'pipeline worker: {name} processed {len(outcome)} item(s)')
        return outcome or []
    except Exception:  # noqa: BLE001
        logfire.exception(f'pipeline worker: {name} failed')
        return []


async def run_worker(settings: Settings, stop: asyncio.Event, wake: asyncio.Event) -> None:
    """Loop until `stop` is set, running the full pipeline each interval. Detection and reviewer
    drafting are extraction/matching/drafting tasks, not judgment, so the worker always uses the
    fast/local model."""
    logfire.info('pipeline worker started', interval=settings.parse_worker_interval_seconds)
    creds = fast_llm_credentials(settings)
    while not stop.is_set():
        wake.clear()
        parsed = await _run_stage('parse', process_pending_parses(settings, creds))
        await _run_stage('evaluate_tender', process_pending_evaluations(creds, settings, tender_repository(settings)))
        await _run_stage('evaluate_bid', process_pending_evaluations(creds, settings, bid_repository(settings)))
        if len(parsed) >= settings.parse_batch_size:
            continue
        try:
            await asyncio.wait_for(wake.wait(), timeout=settings.parse_worker_interval_seconds)
        except asyncio.TimeoutError:
            pass
    logfire.info('pipeline worker stopped')
