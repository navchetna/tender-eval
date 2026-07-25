"""Data models for the async PDF parsing stage."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ParseStatus(StrEnum):
    """Terminal + in-flight states reported by the parser API."""

    pending = 'PENDING'
    running = 'RUNNING'
    completed = 'COMPLETED'
    failed = 'FAILED'


class PendingFile(BaseModel):
    """A file_repository row that has been claimed for parsing."""

    file_id: str
    file_name: str
    drive_file_id: str
    mime_type: str
    version_folder_id: str
    parse_attempts: int


class ParseArtifacts(BaseModel):
    """
    Drive locations of the parser's output, stored back into file_repository.parse_artifacts.

    The concrete artifact set (tree json, toc, markdown, images) is filled in once the
    parser response schema is finalised. `extra` keeps any additional artifacts flexible.
    """

    parsed_folder_id: str
    images_folder_id: str | None = None
    toc_content: str | None = None  # raw TOC text stored directly in postgres
    entries: dict[str, dict[str, str]] = {}  # artifact_name -> {id, link}


class ParseOutcome(BaseModel):
    """Result of processing a single file."""

    file_id: str
    file_name: str
    status: ParseStatus
    parse_job_id: str | None = None
    parse_error: str | None = None
    completed_at: datetime | None = None
