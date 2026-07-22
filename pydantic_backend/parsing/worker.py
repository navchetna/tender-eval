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
from .service import process_pending as process_pending_parses


async def _run_stage(name: str, coro) -> None:
    """Run one pipeline stage; a failure here must never stop the other stages or the loop
    itself (matches the per-file/per-batch exception-swallowing already used in
    evaluation/service.py and the previous version of this worker)."""
    try:
        outcome = await coro
        if outcome:
            logfire.info(f'pipeline worker: {name} processed {len(outcome)} item(s)')
    except Exception:  # noqa: BLE001
        logfire.exception(f'pipeline worker: {name} failed')


async def run_worker(settings: Settings, stop: asyncio.Event) -> None:
    """Loop until `stop` is set, running the full pipeline each interval."""
    logfire.info('pipeline worker started', interval=settings.parse_worker_interval_seconds)
    while not stop.is_set():
        await _run_stage('parse', process_pending_parses(settings))
        await _run_stage('evaluate_tender', process_pending_evaluations(settings, tender_repository(settings)))
        await _run_stage('evaluate_bid', process_pending_evaluations(settings, bid_repository(settings)))
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.parse_worker_interval_seconds)
        except asyncio.TimeoutError:
            pass
    logfire.info('pipeline worker stopped')
