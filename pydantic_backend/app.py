import logfire
from fastapi import FastAPI, HTTPException

from .config import get_settings
from .ingestion.gmail import fetch_unread_pdf_emails
from .ingestion.pipeline import AlreadyIngestedError, persist_gmail_email
from .ingestion.postgres import PostgresRepository
from .observability import configure_observability

configure_observability()
app = FastAPI(title='Tender Repository Ingestion', version='0.2.0')
logfire.instrument_fastapi(app)


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
