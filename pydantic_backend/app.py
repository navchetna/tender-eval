import asyncio
import logfire
from fastapi import FastAPI, HTTPException

from .config import get_settings
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
