import asyncio
import json
from datetime import datetime, timezone

import bcrypt
import logfire
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth.dependencies import get_current_user, get_fast_llm_credentials, get_quality_llm_credentials, invalidate_user_cache, require_admin
from .auth.models import AssignReviewerRequest, CurrentUser, Role
from .config import get_settings
from .db import start_pool, stop_pools
from .evaluation import assignment_notify, tree_utils
from .evaluation.employee_repository import EmailAlreadyExistsError, EmployeeInUseError, EmployeeNotFoundError, EmployeeRepository
from .evaluation.models import DetectionResult, Employee, EmployeeIn, EmployeeUpdate, EvaluationRecord, ReviewDecision, SectionSuggestion, Topic
from .evaluation.models import PendingFile as EvaluationPendingFile
from .evaluation.repository import EvaluationRepository, bid_repository, tender_repository
from .evaluation.service import process_pending as process_pending_evaluations
from .evaluation.service import resend_notification
from .evaluation.service import retry_file as retry_evaluation_file
from .ingestion import drive
from .ingestion.gmail import fetch_unread_pdf_emails
from .ingestion.pipeline import AlreadyIngestedError, persist_gmail_email
from .ingestion.models import FileType, FileTypeUpdate, IncomingEmail, Project, ProjectFileRecord, ProjectIn, StoredFile
from .ingestion.postgres import PostgresRepository
from .llm_credentials import LlmCredentials
from .normalization import compare_client as normalization_compare_client
from .normalization import compliance_service
from .normalization import excel as normalization_excel
from .normalization import llm_result_cache
from .normalization import score_client as normalization_score_client
from .normalization import service as normalization_service
from .normalization.models import ComparisonResult, DefaultPrompts, MatrixData, NormalizedView, PromptOverride, SectionScoreResult
from .observability import configure_observability
from .parsing.models import ParseArtifacts
from .parsing.models import PendingFile as ParsingPendingFile
from .parsing.service import process_pending
from .parsing.service import retry_file as retry_parse_file
from .parsing.worker import run_worker
from .pipeline_detail import FileStageDetail, build_file_stage_detail

configure_observability()
app = FastAPI(title='Tender Repository Ingestion', version='0.3.0')
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

_worker_stop: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


@app.on_event('startup')
async def _start_pool() -> None:
    await start_pool(get_settings())


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


@app.on_event('shutdown')
async def _stop_pool() -> None:
    await stop_pools()


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'flow': 'gmail-to-postgres'}


@app.get('/pipeline/schema')
async def pipeline_schema() -> dict[str, dict[str, dict]]:
    """
    Static Pydantic input/output JSON Schema per pipeline stage, for the workspace's per-file
    stage-detail popover. "Aligned" has no schema — it's a derived readiness flag, not a
    processing stage with its own input/output (see /projects/{id}/files/{id}/stage-detail).
    """
    return {
        'received': {'input': IncomingEmail.model_json_schema(), 'output': StoredFile.model_json_schema()},
        'parsed': {'input': ParsingPendingFile.model_json_schema(), 'output': ParseArtifacts.model_json_schema()},
        'sections': {'input': EvaluationPendingFile.model_json_schema(), 'output': DetectionResult.model_json_schema()},
        'clauses': {'input': SectionSuggestion.model_json_schema(), 'output': ReviewDecision.model_json_schema()},
    }


@app.get('/auth/me')
async def whoami(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Resolve the caller's identity from their HTTP Basic credentials. Used by the frontend
    to turn a typed-in email/password into a session (who is this, what's their role)."""
    return user


@app.post('/setup/database')
async def setup_database() -> dict[str, str]:
    """
    Create/reset schema and bootstrap the one ADMIN account from ADMIN_EMAIL/ADMIN_PASSWORD.
    Unauthenticated on purpose — it's the very first call, before any employee exists.
    """
    settings = get_settings()
    repository = PostgresRepository(settings)
    await repository.initialize()
    admin_password = settings.admin_password.get_secret_value()
    if settings.admin_email and admin_password:
        password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await repository.ensure_admin(settings.admin_email, password_hash)
    return {'status': 'initialized'}


@app.post('/ingestion/poll-gmail')
async def poll_gmail(max_results: int = 20, _admin: CurrentUser = Depends(require_admin)) -> list[dict]:
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
async def parsing_process_pending(
    _admin: CurrentUser = Depends(require_admin), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> list[dict]:
    """Claim a batch of unparsed PDFs, run them through the parser, and store results. Each
    file that parses successfully also triggers its own section detection immediately (see
    parsing/service.py), rather than waiting for the worker's next catch-up tick."""
    try:
        outcomes = await process_pending(get_settings(), creds)
        return [outcome.model_dump(mode='json') for outcome in outcomes]
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


async def _run_evaluation_process_pending(creds: LlmCredentials, repository: EvaluationRepository) -> list[str]:
    try:
        return await process_pending_evaluations(creds, get_settings(), repository)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


async def _ensure_project_access(project_id: str, user: CurrentUser) -> None:
    """Admins can access any project; reviewers only the project they're assigned to."""
    if user.role == Role.admin:
        return
    project = await PostgresRepository(get_settings()).get_project(project_id)
    assigned_to = str(project['assigned_to']) if project and project.get('assigned_to') else None
    if assigned_to != user.employee_id:
        raise HTTPException(403, 'You are not assigned to this project')


async def _run_evaluation_notify(
    creds: LlmCredentials, repository: EvaluationRepository, evaluation_id: str, user: CurrentUser
) -> dict[str, bool]:
    record = await repository.get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')
    await _ensure_project_access(record.project_id, user)
    try:
        sent = await resend_notification(creds, get_settings(), repository, evaluation_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {'sent': sent}


async def _run_evaluation_review(
    repository: EvaluationRepository, evaluation_id: str, decision: ReviewDecision, user: CurrentUser
) -> EvaluationRecord:
    """Approve the AI-suggested section, or reject and replace it with a corrected TOC heading."""
    record = await repository.get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')
    await _ensure_project_access(record.project_id, user)

    if decision.corrected_heading:
        file = await PostgresRepository(get_settings()).get_file(record.file_id)
        content: str | None = None
        if file is not None and file.get('parse_artifacts'):
            entries = (file['parse_artifacts'] or {}).get('entries') or {}
            tree_entry = next((v for k, v in entries.items() if k.endswith('_output_tree.json')), None)
            if tree_entry and tree_entry.get('id'):
                tree_bytes = await asyncio.to_thread(drive.download_file, get_settings(), tree_entry['id'])
                _, content = tree_utils.find_section(tree_bytes, decision.corrected_heading)
        await repository.correct(evaluation_id, decision.topic, user.employee_id, decision.corrected_heading, content)
    else:
        await repository.approve(evaluation_id, decision.topic, user.employee_id)

    # Every cached normalization result (view/score/compare/matrix) is a pure function of
    # approved section content for this project/version — any approval or correction
    # invalidates all of them.
    await llm_result_cache.invalidate(get_settings(), record.project_id, record.version)

    updated = await repository.get_evaluation(evaluation_id)
    assert updated is not None
    return updated


def _pending_filter(user: CurrentUser) -> str | None:
    return None if user.role == Role.admin else user.employee_id


# --- Tender document section evaluation ---------------------------------------------

@app.post('/evaluation/tender/process-pending')
async def evaluation_tender_process_pending(
    _admin: CurrentUser = Depends(require_admin), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> list[str]:
    """Detect technical/price sections for PARSED tender files that have no evaluation yet, and notify the reviewer."""
    return await _run_evaluation_process_pending(creds, tender_repository(get_settings()))


@app.get('/evaluation/tender/pending')
async def evaluation_tender_list_pending(user: CurrentUser = Depends(get_current_user)) -> list[EvaluationRecord]:
    """List tender evaluations still awaiting a technical or price review decision.
    Reviewers only see evaluations for their assigned project(s); admins see everything."""
    return await tender_repository(get_settings()).list_pending_review(_pending_filter(user))


@app.get('/evaluation/tender')
async def evaluation_tender_list_by_project(
    project_id: str = Query(...), version: int = Query(...), user: CurrentUser = Depends(get_current_user)
) -> list[EvaluationRecord]:
    """All tender evaluations (normally 0 or 1) for a project/version, regardless of review status."""
    await _ensure_project_access(project_id, user)
    return await tender_repository(get_settings()).list_by_project_version(project_id, version)


@app.get('/evaluation/tender/{evaluation_id}')
async def evaluation_tender_get(evaluation_id: str, user: CurrentUser = Depends(get_current_user)) -> EvaluationRecord:
    record = await tender_repository(get_settings()).get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')
    await _ensure_project_access(record.project_id, user)
    return record


@app.post('/evaluation/tender/{evaluation_id}/notify')
async def evaluation_tender_notify(
    evaluation_id: str, user: CurrentUser = Depends(get_current_user), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> dict[str, bool]:
    """Re-send the reviewer notification email (useful if reviewer_email was unset on first run)."""
    return await _run_evaluation_notify(creds, tender_repository(get_settings()), evaluation_id, user)


@app.post('/evaluation/tender/{evaluation_id}/review')
async def evaluation_tender_review(
    evaluation_id: str, decision: ReviewDecision, user: CurrentUser = Depends(get_current_user)
) -> EvaluationRecord:
    return await _run_evaluation_review(tender_repository(get_settings()), evaluation_id, decision, user)


# --- Bid document section evaluation (same flow, per bid file) ----------------------
# NOTE: this section (and its bare-path siblings below) must stay registered BEFORE the
# deprecated `/evaluation/{evaluation_id}` catch-all — Starlette matches routes in
# registration order, and a single dynamic segment like `{evaluation_id}` will otherwise
# swallow literal-looking paths such as `/evaluation/bid` before this section is ever reached.

@app.post('/evaluation/bid/process-pending')
async def evaluation_bid_process_pending(
    _admin: CurrentUser = Depends(require_admin), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> list[str]:
    """Detect technical/price sections for PARSED bid files that have no evaluation yet, and notify the reviewer."""
    return await _run_evaluation_process_pending(creds, bid_repository(get_settings()))


@app.get('/evaluation/bid/pending')
async def evaluation_bid_list_pending(user: CurrentUser = Depends(get_current_user)) -> list[EvaluationRecord]:
    """List bid evaluations still awaiting a technical or price review decision.
    Reviewers only see evaluations for their assigned project(s); admins see everything."""
    return await bid_repository(get_settings()).list_pending_review(_pending_filter(user))


@app.get('/evaluation/bid')
async def evaluation_bid_list_by_project(
    project_id: str = Query(...), version: int = Query(...), user: CurrentUser = Depends(get_current_user)
) -> list[EvaluationRecord]:
    """All bid evaluations (one per bidder file) for a project/version, regardless of review status."""
    await _ensure_project_access(project_id, user)
    return await bid_repository(get_settings()).list_by_project_version(project_id, version)


@app.get('/evaluation/bid/{evaluation_id}')
async def evaluation_bid_get(evaluation_id: str, user: CurrentUser = Depends(get_current_user)) -> EvaluationRecord:
    record = await bid_repository(get_settings()).get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')
    await _ensure_project_access(record.project_id, user)
    return record


@app.post('/evaluation/bid/{evaluation_id}/notify')
async def evaluation_bid_notify(
    evaluation_id: str, user: CurrentUser = Depends(get_current_user), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> dict[str, bool]:
    return await _run_evaluation_notify(creds, bid_repository(get_settings()), evaluation_id, user)


@app.post('/evaluation/bid/{evaluation_id}/review')
async def evaluation_bid_review(
    evaluation_id: str, decision: ReviewDecision, user: CurrentUser = Depends(get_current_user)
) -> EvaluationRecord:
    return await _run_evaluation_review(bid_repository(get_settings()), evaluation_id, decision, user)


# --- Deprecated aliases: bare /evaluation/... routes, kept for backward compatibility ---
# Prefer the /evaluation/tender/... routes above for new integrations.

@app.post('/evaluation/process-pending')
async def evaluation_process_pending(
    _admin: CurrentUser = Depends(require_admin), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> list[str]:
    return await _run_evaluation_process_pending(creds, tender_repository(get_settings()))


@app.get('/evaluation/pending')
async def evaluation_list_pending(user: CurrentUser = Depends(get_current_user)) -> list[EvaluationRecord]:
    return await tender_repository(get_settings()).list_pending_review(_pending_filter(user))


@app.get('/evaluation/pending/count')
async def evaluation_pending_count(user: CurrentUser = Depends(get_current_user)) -> dict[str, int]:
    """Backs the review-queue sidebar badge: tender + bid evaluations (of either doc type)
    still awaiting a technical/price decision. Admins get the total across every project;
    reviewers only count what's assigned to them — same scoping as list_pending_review."""
    settings = get_settings()
    filter_id = _pending_filter(user)
    tender_count = await tender_repository(settings).count_pending_review(filter_id)
    bid_count = await bid_repository(settings).count_pending_review(filter_id)
    return {'count': tender_count + bid_count}


@app.get('/evaluation/{evaluation_id}')
async def evaluation_get(evaluation_id: str, user: CurrentUser = Depends(get_current_user)) -> EvaluationRecord:
    record = await tender_repository(get_settings()).get_evaluation(evaluation_id)
    if record is None:
        raise HTTPException(404, 'Evaluation not found')
    await _ensure_project_access(record.project_id, user)
    return record


@app.post('/evaluation/{evaluation_id}/notify')
async def evaluation_notify(
    evaluation_id: str, user: CurrentUser = Depends(get_current_user), creds: LlmCredentials = Depends(get_fast_llm_credentials)
) -> dict[str, bool]:
    return await _run_evaluation_notify(creds, tender_repository(get_settings()), evaluation_id, user)


@app.post('/evaluation/{evaluation_id}/review')
async def evaluation_review(
    evaluation_id: str, decision: ReviewDecision, user: CurrentUser = Depends(get_current_user)
) -> EvaluationRecord:
    return await _run_evaluation_review(tender_repository(get_settings()), evaluation_id, decision, user)


# --- Normalized tender-vs-bid comparison view (computed on demand, nothing persisted) ---

async def _build_normalized_view(
    creds: LlmCredentials, project_id: str, version: int, topic: Topic, user: CurrentUser
) -> NormalizedView:
    """Backs /technical, /price, and /export. Building this runs a row/header alignment LLM
    call per approved bid, so the result is cached (see llm_result_cache) and only recomputed
    once a section is (re)approved or corrected for this project/version."""
    await _ensure_project_access(project_id, user)
    settings = get_settings()
    cached = await llm_result_cache.get_cached(settings, project_id, version, 'view', topic.value)
    if cached is not None:
        return NormalizedView.model_validate(cached)
    try:
        view = await normalization_service.build_view(
            creds, tender_repository(settings), bid_repository(settings), project_id, version, topic,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await llm_result_cache.save_cached(settings, project_id, version, 'view', view.model_dump(mode='json'), topic.value)
    return view


@app.get('/normalization/{project_id}/{version}/technical')
async def normalization_technical(
    project_id: str, version: int,
    user: CurrentUser = Depends(get_current_user), creds: LlmCredentials = Depends(get_quality_llm_credentials),
) -> NormalizedView:
    """Tender technical requirements next to each approved bid's matched values, computed fresh."""
    return await _build_normalized_view(creds, project_id, version, Topic.technical, user)


@app.get('/normalization/{project_id}/{version}/price')
async def normalization_price(
    project_id: str, version: int,
    user: CurrentUser = Depends(get_current_user), creds: LlmCredentials = Depends(get_quality_llm_credentials),
) -> NormalizedView:
    """Tender price line items next to each approved bid's matched values, computed fresh."""
    return await _build_normalized_view(creds, project_id, version, Topic.price, user)


@app.get('/normalization/{project_id}/{version}/export')
async def normalization_export(
    project_id: str, version: int,
    user: CurrentUser = Depends(get_current_user), creds: LlmCredentials = Depends(get_quality_llm_credentials),
) -> StreamingResponse:
    """Export both the Technical and Price comparison views as a single .xlsx workbook."""
    await _ensure_project_access(project_id, user)
    views: list[NormalizedView] = []
    for topic in (Topic.technical, Topic.price):
        try:
            views.append(await _build_normalized_view(creds, project_id, version, topic, user))
        except HTTPException:
            continue  # skip a topic that isn't approved/available yet; export whatever is ready
    if not views:
        raise HTTPException(422, 'Neither technical nor price sections are approved yet for this project/version')

    workbook_bytes = normalization_excel.build_workbook(views)
    filename = f'compliance-{project_id}-v{version}.xlsx'
    return StreamingResponse(
        iter([workbook_bytes]),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@app.get('/normalization/prompts')
async def normalization_prompts(user: CurrentUser = Depends(get_current_user)) -> DefaultPrompts:
    """The default prompts behind Technical/Price scoring and the cross-bid comparison step —
    lets the compliance-matrix UI show a reviewer what will run before they choose to override it."""
    return DefaultPrompts(
        technical=normalization_score_client.DEFAULT_SYSTEM_PROMPT,
        price=normalization_score_client.DEFAULT_SYSTEM_PROMPT,
        comparison=normalization_compare_client.DEFAULT_SYSTEM_PROMPT,
    )


@app.post('/normalization/{project_id}/{version}/score/{topic}')
async def normalization_score(
    project_id: str, version: int, topic: Topic,
    body: PromptOverride | None = None,
    user: CurrentUser = Depends(get_current_user),
    creds: LlmCredentials = Depends(get_quality_llm_credentials),
) -> SectionScoreResult:
    """Ask an LLM to holistically score every approved bidder's whole technical or price
    section against the tender, with reasoning per bidder and a comparative narrative across
    all of them. Cached the same way as the normalized view — see llm_result_cache — unless a
    custom prompt override is given, in which case the result is computed fresh and not cached,
    since it's no longer a pure function of the approved section content alone."""
    await _ensure_project_access(project_id, user)
    settings = get_settings()
    custom_prompt = (body.prompt or '').strip() if body else ''
    if not custom_prompt:
        cached = await llm_result_cache.get_cached(settings, project_id, version, 'score', topic.value)
        if cached is not None:
            return SectionScoreResult.model_validate(cached)
    view = await _build_normalized_view(creds, project_id, version, topic, user)
    try:
        result = await normalization_score_client.score_section(creds, view, custom_prompt or None)
    except Exception as exc:  # noqa: BLE001 — model output failures happen; give a retryable 502, not a 500
        raise HTTPException(502, 'The model failed to produce a valid score — try again.') from exc
    if not custom_prompt:
        await llm_result_cache.save_cached(settings, project_id, version, 'score', result.model_dump(mode='json'), topic.value)
    return result


@app.post('/normalization/{project_id}/{version}/compare')
async def normalization_compare(
    project_id: str, version: int,
    body: PromptOverride | None = None,
    user: CurrentUser = Depends(get_current_user),
    creds: LlmCredentials = Depends(get_quality_llm_credentials),
) -> ComparisonResult:
    """Detailed overall comparison across BOTH technical and price sections together: an
    extended pros/cons/precautions assessment per bidder plus one recommended award. Whichever
    section(s) are approved so far are used; a topic that isn't approved yet is simply left out
    rather than failing the whole request. Cached — see llm_result_cache — same as the other
    normalization results, unless a custom prompt override is given, in which case the result
    is computed fresh and not cached."""
    await _ensure_project_access(project_id, user)
    settings = get_settings()
    custom_prompt = (body.prompt or '').strip() if body else ''
    if not custom_prompt:
        cached = await llm_result_cache.get_cached(settings, project_id, version, 'compare')
        if cached is not None:
            return ComparisonResult.model_validate(cached)

    async def _try_view(topic: Topic) -> NormalizedView | None:
        try:
            return await _build_normalized_view(creds, project_id, version, topic, user)
        except HTTPException:
            return None

    technical_view, price_view = await _try_view(Topic.technical), await _try_view(Topic.price)
    if technical_view is None and price_view is None:
        raise HTTPException(422, 'Neither technical nor price sections are approved yet for this project/version')
    try:
        result = await normalization_compare_client.compare_bids(
            creds, project_id, version, technical_view, price_view, custom_prompt or None,
        )
    except Exception as exc:  # noqa: BLE001 — model output failures happen; give a retryable 502, not a 500
        raise HTTPException(502, 'The model failed to produce a valid comparison — try again.') from exc
    if not custom_prompt:
        await llm_result_cache.save_cached(settings, project_id, version, 'compare', result.model_dump(mode='json'))
    return result


@app.get('/normalization/{project_id}/{version}/matrix')
async def normalization_matrix(
    project_id: str, version: int,
    user: CurrentUser = Depends(get_current_user),
    creds: LlmCredentials = Depends(get_quality_llm_credentials),
) -> MatrixData:
    """Technical + price compliance matrix: each requirement row judged compliant/partial/
    non-compliant per bidder by an LLM, built on top of the on-demand normalized view.

    Building this runs dozens of LLM calls (row/header alignment plus a judgment per row), so
    the result is cached — see llm_result_cache — and only recomputed once a section is
    (re)approved or corrected for this project/version."""
    await _ensure_project_access(project_id, user)
    settings = get_settings()
    cached = await llm_result_cache.get_cached(settings, project_id, version, 'matrix')
    if cached is not None:
        return MatrixData.model_validate(cached)
    try:
        matrix = await compliance_service.build_matrix(
            creds, tender_repository(settings), bid_repository(settings), project_id, version,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await llm_result_cache.save_cached(settings, project_id, version, 'matrix', matrix.model_dump(mode='json'))
    return matrix


# --- Projects: creation, direct document upload, and per-project reviewer assignment ---

def _to_file_record(row: dict) -> ProjectFileRecord:
    return ProjectFileRecord(
        file_id=str(row['file_id']),
        project_id=str(row['project_id']),
        version=row['version'],
        file_name=row['file_name'],
        file_type=row['file_type'],
        processing_status=row['processing_status'],
        drive_web_link=row['drive_web_link'],
        parse_error=row['parse_error'],
        parse_toc=row['parse_toc'],
        detection_error=row['detection_error'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def _to_project(row: dict) -> Project:
    return Project(
        project_id=str(row['project_id']),
        project_code=row['project_code'],
        project_name=row['project_name'],
        current_version=row['current_version'],
        status=row['status'],
        assigned_to=str(row['assigned_to']) if row['assigned_to'] else None,
        evaluation_completed=row.get('evaluation_completed', False),
    )


@app.get('/projects')
async def list_projects(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """Admins see every project; reviewers only see the project(s) assigned to them."""
    repository = PostgresRepository(get_settings())
    rows = await repository.list_projects(None if user.role == Role.admin else user.employee_id)
    return [
        {
            'project_id': str(row['project_id']),
            'project_code': row['project_code'],
            'project_name': row['project_name'],
            'current_version': row['current_version'],
            'status': row['status'],
            'assigned_to': str(row['assigned_to']) if row['assigned_to'] else None,
            'evaluation_completed': row['evaluation_completed'],
        }
        for row in rows
    ]


@app.post('/projects')
async def create_project(body: ProjectIn, _admin: CurrentUser = Depends(require_admin)) -> Project:
    """Create a project directly from the console — no email required. Its Drive folder is
    created lazily on first file upload, same as the email-ingestion path."""
    try:
        row = await PostgresRepository(get_settings()).create_project(body.project_code, body.project_name)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _to_project(row)


@app.delete('/projects/{project_id}', status_code=204)
async def delete_project(project_id: str, _admin: CurrentUser = Depends(require_admin)) -> None:
    """Permanently delete a project and every file/evaluation scoped to it. Admin-only."""
    deleted = await PostgresRepository(get_settings()).delete_project(project_id)
    if not deleted:
        raise HTTPException(404, 'Project not found')


@app.get('/projects/{project_id}/files')
async def list_project_files(
    project_id: str, user: CurrentUser = Depends(get_current_user)
) -> list[ProjectFileRecord]:
    """Every file_repository row for a project (tender + all bids, every version). Backs the
    frontend's document lists (Workspace, Ops) — reviewers are scoped to their assigned project."""
    await _ensure_project_access(project_id, user)
    rows = await PostgresRepository(get_settings()).list_files(project_id)
    return [_to_file_record(row) for row in rows]


@app.post('/projects/{project_id}/files')
async def upload_project_files(
    project_id: str,
    file_type: FileType = Form(...),
    new_version: bool = Form(...),
    files: list[UploadFile] = File(...),
    _admin: CurrentUser = Depends(require_admin),
) -> list[ProjectFileRecord]:
    """
    Upload one or more PDFs directly (tender or bid — chosen explicitly, not filename-guessed)
    without going through Gmail. `new_version` starts a fresh version (new Drive subfolder);
    otherwise the files are added into the current version, reusing its existing Drive folder.
    """
    if not files:
        raise HTTPException(422, 'No files provided')

    settings = get_settings()
    repository = PostgresRepository(settings)
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')

    version_folder_name: str | None = None
    version_folder_id: str | None = None
    if not new_version and project['current_version'] > 0:
        version = project['current_version']
        version_folder_id = await repository.get_version_folder_id(project_id, version)

    if version_folder_id is None:
        # Either explicitly starting a new version, or there's no existing folder to reuse
        # (brand-new project, or "add to current" requested before any file exists yet).
        version = project['current_version'] + 1 if (new_version or project['current_version'] == 0) else project['current_version']
        _, version_folder_id, version_folder_name = await asyncio.to_thread(
            drive.ensure_project_folder, settings, project['project_code'], project['project_name'],
            version, datetime.now(timezone.utc),
        )
        await repository.set_current_version(project_id, version)

    created: list[ProjectFileRecord] = []
    for upload in files:
        content = await upload.read()
        file_name = upload.filename or 'document.pdf'
        mime_type = upload.content_type or 'application/pdf'
        drive_file_id, drive_web_link = await asyncio.to_thread(
            drive.upload_bytes, settings, file_name, content, mime_type, version_folder_id,
        )
        row = await repository.insert_direct_file(
            project_id=project_id,
            project_code=project['project_code'],
            project_name=project['project_name'],
            version=version,
            version_folder_name=version_folder_name,
            file_name=file_name,
            file_type=file_type.value,
            mime_type=mime_type,
            content=content,
            drive_file_id=drive_file_id,
            drive_folder_id=version_folder_id,
            drive_web_link=drive_web_link,
        )
        created.append(_to_file_record(row))
    return created


@app.patch('/projects/{project_id}/files/{file_id}')
async def update_project_file_type(
    project_id: str, file_id: str, body: FileTypeUpdate, _admin: CurrentUser = Depends(require_admin)
) -> ProjectFileRecord:
    """Correct a file's tender/bid classification after upload."""
    settings = get_settings()
    repository = PostgresRepository(settings)
    file = await repository.get_file(file_id)
    if file is None or str(file['project_id']) != project_id:
        raise HTTPException(404, 'File not found')
    row = await repository.update_file_type(file_id, body.file_type.value)
    assert row is not None
    # update_file_type may have just dropped this file's evaluation under its old
    # classification — any cached view/score/compare/matrix for this project/version could
    # have been built from that now-gone row.
    await llm_result_cache.invalidate(settings, project_id, row['version'])
    return _to_file_record(row)


async def _get_owned_file(project_id: str, file_id: str, user: CurrentUser) -> dict:
    await _ensure_project_access(project_id, user)
    file = await PostgresRepository(get_settings()).get_file(file_id)
    if file is None or str(file['project_id']) != project_id:
        raise HTTPException(404, 'File not found')
    return file


@app.get('/projects/{project_id}/files/{file_id}/pdf')
async def get_file_pdf(project_id: str, file_id: str, user: CurrentUser = Depends(get_current_user)) -> StreamingResponse:
    """Stream the original PDF straight from Drive, so the console can render it inline
    without requiring the file to be publicly shared."""
    file = await _get_owned_file(project_id, file_id, user)
    if not file.get('drive_file_id'):
        raise HTTPException(404, 'No source PDF stored for this file')
    content = await asyncio.to_thread(drive.download_file, get_settings(), file['drive_file_id'])
    return StreamingResponse(
        iter([content]),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename="{file["file_name"]}"',
            # A file's stored PDF bytes never change once uploaded (a new version is a new
            # file_id, not an in-place edit), so the browser can cache this response
            # indefinitely and skip both the request and the Drive re-download entirely.
            'Cache-Control': 'private, max-age=31536000, immutable',
        },
    )


@app.get('/projects/{project_id}/files/{file_id}/tree')
async def get_file_tree(project_id: str, file_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """The parser's output_tree.json for this file, if parsing has produced one yet."""
    file = await _get_owned_file(project_id, file_id, user)
    entries = ((file.get('parse_artifacts') or {}).get('entries')) or {}
    tree_entry = next((v for k, v in entries.items() if k.endswith('_output_tree.json')), None)
    if not tree_entry or not tree_entry.get('id'):
        raise HTTPException(404, 'No parsed tree available for this file yet')
    tree_bytes = await asyncio.to_thread(drive.download_file, get_settings(), tree_entry['id'])
    return json.loads(tree_bytes)


@app.get('/projects/{project_id}/files/{file_id}/images')
async def list_file_images(project_id: str, file_id: str, user: CurrentUser = Depends(get_current_user)) -> list[str]:
    """Names of the figures the parser extracted for this file (see parsing/service.py's
    `page_{page}_{name}` upload convention) — empty if parsing hasn't produced any yet."""
    file = await _get_owned_file(project_id, file_id, user)
    entries = ((file.get('parse_artifacts') or {}).get('entries')) or {}
    return sorted(name for name in entries if name.startswith('page_'))


@app.get('/projects/{project_id}/files/{file_id}/images/{image_name}')
async def get_file_image(
    project_id: str, file_id: str, image_name: str, user: CurrentUser = Depends(get_current_user)
) -> StreamingResponse:
    """Stream one extracted figure straight from Drive, by the name returned from the
    `/images` listing above."""
    file = await _get_owned_file(project_id, file_id, user)
    entries = ((file.get('parse_artifacts') or {}).get('entries')) or {}
    entry = entries.get(image_name)
    if not entry or not entry.get('id'):
        raise HTTPException(404, 'Image not found for this file')
    content = await asyncio.to_thread(drive.download_file, get_settings(), entry['id'])
    return StreamingResponse(
        iter([content]),
        media_type='image/png',
        headers={'Cache-Control': 'private, max-age=31536000, immutable'},
    )


@app.get('/projects/{project_id}/files/{file_id}/stage-detail')
async def get_file_stage_detail(
    project_id: str, file_id: str, user: CurrentUser = Depends(get_current_user)
) -> FileStageDetail:
    """Actual input/output/error for each pipeline stage this file has gone through so far —
    pairs with the static shapes from GET /pipeline/schema. Backs the workspace's per-stage
    detail popover."""
    file = await _get_owned_file(project_id, file_id, user)
    settings = get_settings()
    evaluation = None
    if file['file_type'] == FileType.tender.value:
        evaluation = await tender_repository(settings).get_evaluation_by_file(file_id)
    elif file['file_type'] == FileType.bid.value:
        evaluation = await bid_repository(settings).get_evaluation_by_file(file_id)
    return build_file_stage_detail(file, evaluation)


@app.post('/projects/{project_id}/files/{file_id}/retry')
async def retry_file_stage(
    project_id: str,
    file_id: str,
    user: CurrentUser = Depends(get_current_user),
    creds: LlmCredentials = Depends(get_fast_llm_credentials),
) -> ProjectFileRecord:
    """
    Manually retry whichever pipeline stage this file is currently stuck on — Parsed
    (PARSE_FAILED, bypassing the worker's automatic attempt cap) or Sections (PARSED with no
    evaluation row yet, e.g. after a detection error). Reads the file's current state fresh
    so it always targets whatever's actually stuck, without the caller needing to say which
    stage. A stage that fails again leaves its error field set (parse_error/detection_error)
    for the stage-detail popover to surface — that's a normal retry outcome, not a 5xx.
    """
    file = await _get_owned_file(project_id, file_id, user)
    settings = get_settings()
    try:
        if file['processing_status'] == 'PARSE_FAILED':
            await retry_parse_file(settings, file_id, creds)
        elif file['file_type'] in (FileType.tender.value, FileType.bid.value):
            repository = tender_repository(settings) if file['file_type'] == FileType.tender.value else bid_repository(settings)
            await retry_evaluation_file(creds, settings, repository, file_id)
        else:
            raise ValueError('Nothing to retry for this file')
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    updated = await _get_owned_file(project_id, file_id, user)
    return _to_file_record(updated)


@app.post('/projects/{project_id}/assign')
async def assign_project(
    project_id: str, body: AssignReviewerRequest, _admin: CurrentUser = Depends(require_admin)
) -> dict:
    """Delegate review of an entire project (all its files/versions) to one reviewer, and
    email them a summary of the project's current status and what's pending their review."""
    settings = get_settings()
    row = await PostgresRepository(settings).assign_project(project_id, body.employee_id)
    if row is None:
        raise HTTPException(404, 'Project not found')

    notified = False
    employee = await EmployeeRepository(settings).get_employee(body.employee_id)
    if employee is not None:
        notified = await assignment_notify.notify_assignment(settings, row, employee.email)

    return {'project_id': str(row['project_id']), 'assigned_to': str(row['assigned_to']), 'notified': notified}


@app.post('/employees')
async def create_employee(employee: EmployeeIn, _admin: CurrentUser = Depends(require_admin)) -> Employee:
    return await EmployeeRepository(get_settings()).create_employee(employee)


@app.get('/employees')
async def list_employees(_admin: CurrentUser = Depends(require_admin)) -> list[Employee]:
    return await EmployeeRepository(get_settings()).list_employees()


@app.patch('/employees/{employee_id}')
async def update_employee(
    employee_id: str, update: EmployeeUpdate, _admin: CurrentUser = Depends(require_admin)
) -> Employee:
    """Edit an employee's name/email/role, and/or reset their password. Admin-only."""
    try:
        result = await EmployeeRepository(get_settings()).update_employee(employee_id, update)
        invalidate_user_cache()  # a cached role/password must never outlive the change that invalidated it
        return result
    except EmployeeNotFoundError as exc:
        raise HTTPException(404, 'Employee not found') from exc
    except EmailAlreadyExistsError as exc:
        raise HTTPException(409, 'That email is already in use by another employee') from exc


@app.delete('/employees/{employee_id}', status_code=204)
async def delete_employee(employee_id: str, _admin: CurrentUser = Depends(require_admin)) -> None:
    """Remove an employee. Admin-only. Fails with 409 if they're still assigned to a
    project or referenced by a recorded review decision — unassign/reassign those first."""
    try:
        await EmployeeRepository(get_settings()).delete_employee(employee_id)
        invalidate_user_cache()
    except EmployeeNotFoundError as exc:
        raise HTTPException(404, 'Employee not found') from exc
    except EmployeeInUseError as exc:
        raise HTTPException(
            409,
            'Cannot delete: this employee is still assigned to a project or has recorded '
            'reviews. Reassign their project(s) first.',
        ) from exc

