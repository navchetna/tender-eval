"""
Background pipeline worker: periodically parses pending PDFs, then runs payment/service
compliance section-detection for newly-parsed circular and submission files. This is what lets
uploaded documents progress on their own (RECEIVED -> PARSED -> SUGGESTED evaluations) without
an admin manually clicking "process pending" after every upload.
"""
from __future__ import annotations

import asyncio

import logfire

from ..config import Settings
from ..evaluation.repository import circular_repository, submission_repository
from ..evaluation.service import process_pending as process_pending_evaluations
from ..llm_credentials import worker_llm_credentials
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
    """Loop until `stop` is set, running the full pipeline each interval. This loop has no
    logged-in employee to attribute LLM calls to, so it uses its own dedicated worker key
    (LITELLM_WORKER_API_KEY) rather than any employee's."""
    logfire.info('pipeline worker started', interval=settings.parse_worker_interval_seconds)
    creds = worker_llm_credentials(settings)
    while not stop.is_set():
        await _run_stage('parse', process_pending_parses(settings, creds))
        await _run_stage('evaluate_circular', process_pending_evaluations(creds, settings, circular_repository(settings)))
        await _run_stage('evaluate_submission', process_pending_evaluations(creds, settings, submission_repository(settings)))
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.parse_worker_interval_seconds)
        except asyncio.TimeoutError:
            pass
    logfire.info('pipeline worker stopped')
