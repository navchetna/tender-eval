"""
Emails a reviewer when a project is assigned to them, summarizing the project's current
per-file status and which technical/price sections are still awaiting their review.

Plain templated text — no LLM involved (unlike notify_agent.py's drafted reviewer emails for
newly-suggested sections). Sending is best-effort: a failure here (e.g. the Gmail OAuth token
lacks the send scope) must never block the assignment itself from succeeding.
"""
from __future__ import annotations

import asyncio

import logfire

from ..config import Settings
from ..ingestion import gmail
from ..ingestion.postgres import PostgresRepository
from .models import EvaluationRecord
from .repository import bid_repository, tender_repository


def _pending_lines(label: str, evaluations: list[EvaluationRecord]) -> list[str]:
    lines: list[str] = []
    for e in evaluations:
        pending_topics = []
        if e.technical_status == 'SUGGESTED':
            pending_topics.append('technical')
        if e.price_status == 'SUGGESTED':
            pending_topics.append('price')
        if pending_topics:
            lines.append(f'  - {e.file_name} ({label}): {", ".join(pending_topics)} section(s) awaiting review')
    return lines


async def _build_email(settings: Settings, project: dict) -> tuple[str, str]:
    project_id = str(project['project_id'])
    version = project['current_version']

    subject = f"Project assigned: {project['project_code']} — {project['project_name']}"

    if version == 0:
        body = (
            f"You have been assigned to review {project['project_name']} ({project['project_code']}).\n\n"
            'No documents have been uploaded yet.'
        )
        return subject, body

    files = await PostgresRepository(settings).list_files(project_id)
    current_files = [f for f in files if f['version'] == version]
    tender_evals = await tender_repository(settings).list_by_project_version(project_id, version)
    bid_evals = await bid_repository(settings).list_by_project_version(project_id, version)

    status_lines = [f'Version {version}:']
    for f in current_files:
        role = {'TENDER': 'Tender', 'BID': 'Bid'}.get(f['file_type'], f['file_type'])
        status_lines.append(f"  - {role}: {f['file_name']} — {f['processing_status']}")

    pending_lines = _pending_lines('tender', tender_evals) + _pending_lines('bid', bid_evals)

    body_parts = [
        f"You have been assigned to review {project['project_name']} ({project['project_code']}).",
        '',
        'Current status:',
        *status_lines,
        '',
        'Pending your review:' if pending_lines else 'Nothing pending — all sections already reviewed for this version.',
        *pending_lines,
    ]
    return subject, '\n'.join(body_parts)


async def notify_assignment(settings: Settings, project: dict, reviewer_email: str) -> bool:
    """Send the assignment email; returns True if sent, False if it failed (never raises)."""
    try:
        subject, body = await _build_email(settings, project)
        await asyncio.to_thread(gmail.send_email, settings, reviewer_email, subject, body)
        return True
    except Exception:  # noqa: BLE001 — best-effort, must not block the assignment
        logfire.exception('assignment notification failed', project_id=str(project['project_id']))
        return False
