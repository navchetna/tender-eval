import asyncio
import logfire
from fastapi import FastAPI, HTTPException

from .config import get_settings
from .evaluation.models import Employee, EmployeeIn, EvaluationRecord, ReviewDecision, Topic
from .evaluation.repository import EvaluationRepository
from .evaluation.service import process_pending as process_pending_evaluations
from .evaluation.service import resend_notification
from .ingestion.gmail import fetch_unread_pdf_emails
from .ingestion.pipeline import AlreadyIngestedError, persist_gmail_email
from .ingestion.postgres import PostgresRepository
from .observability import configure_observability
from .parsing.service import process_pending
from .parsing.worker import run_worker

configure_observability()
app = FastAPI(title='Tender Repository Ingestion', version='0.3.0')
logfire.instrument_fastapi(app)

_worker_stop: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


@app.on_event('startup')
async def _start_worker() -> None:
    global _worker_stop, _worker_task
    settings = get_settings()
    if settings.parse_worker_enabled:
        _worker_stop = asyncio.Event()
        _worker_task = asyncio.create_task(run_worker(settings, _worker_stop))


@app.on_event('shutdown')
async def _stop_worker() -> None:
    if _worker_stop is not None:
        _worker_stop.set()
    if _worker_task is not None:
        await _worker_task


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'flow': 'gmail-to-postgres'}


@app.post('/setup/database')
async def setup_database() -> dict[str, str]:
    await PostgresRepository(get_settings()).initialize()
    return {'status': 'initialized'}


@app.post('/ingestion/poll-gmail')
async def poll_gmail(max_results: int = 20) -> list[dict]:
    """Fetch unread PDF emails and ingest new ones; already-ingested emails are silently skipped."""
    try:
        settings = get_settings()
        repository = PostgresRepository(settings)
        emails = fetch_unread_pdf_emails(settings, max_results=max_results)
        results = []
        for email in emails:
            try:
                result = await persist_gmail_email(email, repository, settings)
                results.append(result.model_dump())
            except AlreadyIngestedError:
                pass  # same email re-fetched because it's still unread — skip silently
        return results
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/parsing/process-pending')
async def parsing_process_pending() -> list[dict]:
    """Claim a batch of unparsed PDFs, run them through the parser, and store results."""
    try:
        outcomes = await process_pending(get_settings())
        return [outcome.model_dump(mode='json') for outcome in outcomes]
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/evaluation/process-pending')
async def evaluation_process_pending() -> list[str]:
    """Detect technical/price sections for PARSED tender files that have no evaluation yet, and notify the reviewer."""
    try:
        return await process_pending_evaluations(get_settings())
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/evaluation/pending')
async def evaluation_list_pending() -> list[EvaluationRecord]:
    """List evaluations still awaiting a technical or price review decision."""
    return await EvaluationRepository(get_settings()).list_pending_review()


@app.get('/evaluation/{evaluation_id}')
async def evaluation_get(evaluation_id: str) -> EvaluationRecord:
    record = await EvaluationRepository(get_settings()).get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')
    return record


@app.post('/evaluation/{evaluation_id}/notify')
async def evaluation_notify(evaluation_id: str) -> dict[str, bool]:
    """Re-send the reviewer notification email (useful if reviewer_email was unset on first run)."""
    try:
        sent = await resend_notification(get_settings(), evaluation_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {'sent': sent}


@app.post('/evaluation/{evaluation_id}/review')
async def evaluation_review(evaluation_id: str, decision: ReviewDecision) -> EvaluationRecord:
    """Approve the AI-suggested section, or reject and replace it with a corrected TOC heading."""
    repository = EvaluationRepository(get_settings())
    record = await repository.get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')

    if decision.corrected_heading:
        file = await PostgresRepository(get_settings()).get_file(record.file_id)
        content: str | None = None
        if file is not None and file.get('parse_artifacts'):
            from .evaluation import tree_utils

            entries = (file['parse_artifacts'] or {}).get('entries') or {}
            tree_entry = next((v for k, v in entries.items() if k.endswith('_output_tree.json')), None)
            if tree_entry and tree_entry.get('id'):
                from .ingestion import drive

                tree_bytes = await asyncio.to_thread(drive.download_file, get_settings(), tree_entry['id'])
                _, content = tree_utils.find_section(tree_bytes, decision.corrected_heading)
        await repository.correct(evaluation_id, decision.topic, decision.employee_id, decision.corrected_heading, content)
    else:
        await repository.approve(evaluation_id, decision.topic, decision.employee_id)

    updated = await repository.get_evaluation(evaluation_id)
    assert updated is not None
    return updated


@app.post('/employees')
async def create_employee(employee: EmployeeIn) -> Employee:
    return await EvaluationRepository(get_settings()).create_employee(employee)


@app.get('/employees')
async def list_employees() -> list[Employee]:
    return await EvaluationRepository(get_settings()).list_employees()
