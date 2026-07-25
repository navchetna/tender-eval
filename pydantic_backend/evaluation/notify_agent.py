"""
Agent-driven reviewer notification.

Instead of deterministically formatting and sending an email, a small pydantic-ai
agent (backed by the LiteLLM gateway) is given a `send_reviewer_email` tool and told what
happened (project, file, suggested sections). The agent drafts the subject/body itself and
decides to call the tool to actually send it.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from ..config import Settings
from ..ingestion.gmail import send_email
from ..llm_agent import build_model
from ..llm_credentials import LlmCredentials


@dataclass
class NotifyDeps:
    settings: Settings
    reviewer_email: str
    sent: bool = False


@dataclass
class BatchNotifyItem:
    """One file's detection result to fold into a single batched reviewer email."""

    file_name: str
    evaluation_id: str
    technical_heading: str | None
    price_heading: str | None


def _build_agent(creds: LlmCredentials) -> Agent[NotifyDeps, str]:
    agent = Agent(
        build_model(creds),
        deps_type=NotifyDeps,
        system_prompt=(
            'You notify a human reviewer that a tender document needs technical/price section '
            'validation. Draft a concise, professional email subject and body summarising the '
            'project, file, and the AI-suggested Technical and Price sections, then call the '
            'send_reviewer_email tool exactly once to actually send it. Do not call the tool more '
            'than once, and do not skip calling it.'
        ),
    )

    @agent.tool
    async def send_reviewer_email(ctx: RunContext[NotifyDeps], subject: str, body: str) -> str:
        """Send the validation-needed notification email to the reviewer's inbox."""
        send_email(ctx.deps.settings, ctx.deps.reviewer_email, subject, body)
        ctx.deps.sent = True
        return 'sent'

    return agent


def _build_batch_agent(creds: LlmCredentials) -> Agent[NotifyDeps, str]:
    agent = Agent(
        build_model(creds),
        deps_type=NotifyDeps,
        system_prompt=(
            'You notify a human reviewer that one or more documents from the same project/version '
            'need technical/price section validation. You will be given a list of documents (each '
            'with its file name, evaluation reference, and AI-suggested Technical/Price section '
            'headings). Draft ONE concise, professional email subject and body that summarises the '
            'project/version and lists every document with its suggested sections and evaluation '
            'reference, so the reviewer can act on all of them from a single email. Then call the '
            'send_reviewer_email tool exactly once to actually send it. Do not call the tool more '
            'than once, and do not skip calling it.'
        ),
    )

    @agent.tool
    async def send_reviewer_email(ctx: RunContext[NotifyDeps], subject: str, body: str) -> str:
        """Send the validation-needed notification email to the reviewer's inbox."""
        send_email(ctx.deps.settings, ctx.deps.reviewer_email, subject, body)
        ctx.deps.sent = True
        return 'sent'

    return agent


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
    """Let the agent draft + send the reviewer notification. Returns True if it actually sent one."""
    if not settings.reviewer_email:
        return False
    deps = NotifyDeps(settings=settings, reviewer_email=settings.reviewer_email)
    agent = _build_agent(creds)
    prompt = (
        f'Project: {project_id}\n'
        f'Version: {version}\n'
        f'File: {file_name}\n'
        f'Evaluation reference: {evaluation_id}\n'
        f'Suggested Technical section: {technical_heading or "(none found)"}\n'
        f'Suggested Price section: {price_heading or "(none found)"}\n'
    )
    await agent.run(prompt, deps=deps)
    return deps.sent


async def notify_reviewer_batch(
    creds: LlmCredentials,
    settings: Settings,
    project_id: str,
    version: int,
    items: list[BatchNotifyItem],
) -> bool:
    """
    Let the agent draft + send ONE reviewer email covering every item (e.g. the tender plus
    all bidder files that got new suggestions in the same processing run). Returns True if
    it actually sent one.
    """
    if not settings.reviewer_email or not items:
        return False
    deps = NotifyDeps(settings=settings, reviewer_email=settings.reviewer_email)
    agent = _build_batch_agent(creds)
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
    await agent.run(prompt, deps=deps)
    return deps.sent

