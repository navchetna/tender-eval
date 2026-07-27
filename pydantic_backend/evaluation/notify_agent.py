"""
Agent-driven reviewer notification.

An LLM agent (backed by the LiteLLM gateway) is given the project/file/suggested-section facts
and drafts the reviewer email's subject and body as a validated structured output — the same
PromptedOutput pattern every other LLM call in this backend uses (see llm_agent.structured_agent).
Sending is then a deterministic step: pydantic-ai guarantees the agent returns a valid
`_EmailDraft` (retrying the model on schema-invalid replies), so the code sends it via Gmail
unconditionally once drafting succeeds. Unlike a tool-call design, there is no path where the
model drafts an email but never sends it — composing the content is the model's only job,
sending isn't something it decides to do.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel

from ..config import Settings
from ..ingestion.gmail import send_email
from ..llm_agent import structured_agent
from ..llm_credentials import LlmCredentials


class _EmailDraft(BaseModel):
    subject: str
    body: str


@dataclass
class BatchNotifyItem:
    """One file's detection result to fold into a single batched reviewer email."""

    file_name: str
    evaluation_id: str
    technical_heading: str | None
    price_heading: str | None


_SINGLE_SYSTEM_PROMPT = (
    'You are drafting an email to notify a human reviewer that a tender document needs '
    'technical/price section validation. Write a concise, professional email subject and body '
    'summarising the project, file, and the AI-suggested Technical and Price sections.'
)

_BATCH_SYSTEM_PROMPT = (
    'You are drafting ONE email to notify a human reviewer that one or more documents from the '
    'same project/version need technical/price section validation. You will be given a list of '
    'documents (each with its file name, evaluation reference, and AI-suggested Technical/Price '
    'section headings). Write ONE concise, professional email subject and body that summarises '
    'the project/version and lists every document with its suggested sections and evaluation '
    'reference, so the reviewer can act on all of them from a single email.'
)


async def notify_reviewer(
    creds: LlmCredentials,
    settings: Settings,
    project_id: str,
    version: int,
    file_name: str,
    evaluation_id: str,
    technical_heading: str | None,
    price_heading: str | None,
) -> bool:
    """Have the LLM draft the reviewer notification, then send it via Gmail. Returns True if sent."""
    if not settings.reviewer_email:
        return False
    prompt = (
        f'Project: {project_id}\n'
        f'Version: {version}\n'
        f'File: {file_name}\n'
        f'Evaluation reference: {evaluation_id}\n'
        f'Suggested Technical section: {technical_heading or "(none found)"}\n'
        f'Suggested Price section: {price_heading or "(none found)"}\n'
    )
    agent = structured_agent(creds, _EmailDraft, _SINGLE_SYSTEM_PROMPT)
    result = await agent.run(prompt)
    await asyncio.to_thread(
        send_email, settings, settings.reviewer_email, result.output.subject, result.output.body
    )
    return True


async def notify_reviewer_batch(
    creds: LlmCredentials,
    settings: Settings,
    project_id: str,
    version: int,
    items: list[BatchNotifyItem],
) -> bool:
    """
    Have the LLM draft ONE reviewer email covering every item (e.g. the tender plus all bidder
    files that got new suggestions in the same processing run), then send it via Gmail.
    Returns True if sent.
    """
    if not settings.reviewer_email or not items:
        return False
    documents = '\n\n'.join(
        f'Document {i}:\n'
        f'  File: {item.file_name}\n'
        f'  Evaluation reference: {item.evaluation_id}\n'
        f'  Suggested Technical section: {item.technical_heading or "(none found)"}\n'
        f'  Suggested Price section: {item.price_heading or "(none found)"}'
        for i, item in enumerate(items, start=1)
    )
    prompt = (
        f'Project: {project_id}\n'
        f'Version: {version}\n'
        f'{len(items)} document(s) need review:\n\n'
        f'{documents}\n'
    )
    agent = structured_agent(creds, _EmailDraft, _BATCH_SYSTEM_PROMPT)
    result = await agent.run(prompt)
    await asyncio.to_thread(
        send_email, settings, settings.reviewer_email, result.output.subject, result.output.body
    )
    return True
