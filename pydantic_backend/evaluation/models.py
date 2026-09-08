"""Data models for the circular payment/service compliance section detection + human review stage."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from ..auth.models import Role


class Topic(StrEnum):
    payment = 'payment'
    service = 'service'


class DocType(StrEnum):
    """Which document a section-detection evaluation is for."""

    circular = 'CIRCULAR'
    submission = 'SUBMISSION'


class ReviewStatus(StrEnum):
    """Lifecycle of a single topic's (payment/service) section suggestion."""

    suggested = 'SUGGESTED'  # AI proposed, awaiting human review
    approved = 'APPROVED'  # human confirmed the AI suggestion, or a correction


class PendingFile(BaseModel):
    """A PARSED file_repository row (circular or submission) that has no evaluation yet."""

    file_id: str
    project_id: str
    version: int
    file_name: str
    parse_toc: str | None
    parse_artifacts: dict | None


class SectionSuggestion(BaseModel):
    """One topic's detected TOC heading + extracted content."""

    heading: str | None = None
    content: str | None = None
    matched: bool = False  # whether the heading could be located in the tree JSON


class DetectionResult(BaseModel):
    payment: SectionSuggestion
    service: SectionSuggestion
    model: str


class EvaluationRecord(BaseModel):
    evaluation_id: str
    file_id: str
    project_id: str
    version: int
    file_name: str | None = None
    detection_model: str | None
    payment_section_title: str | None
    payment_section_content: str | None
    payment_ai_title: str | None = None  # original AI suggestion, preserved even after a correction
    payment_ai_content: str | None = None
    payment_status: ReviewStatus
    payment_corrected: bool
    payment_reviewed_by: str | None
    payment_reviewed_at: datetime | None
    service_section_title: str | None
    service_section_content: str | None
    service_ai_title: str | None = None
    service_ai_content: str | None = None
    service_status: ReviewStatus
    service_corrected: bool
    service_reviewed_by: str | None
    service_reviewed_at: datetime | None
    notified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReviewDecision(BaseModel):
    """Body for POST /evaluation/{evaluation_id}/review. Reviewer identity comes from the
    authenticated HTTP Basic caller, not from this body."""

    topic: Topic
    corrected_heading: str | None = None  # required when the AI suggestion is wrong; picked from the TOC


class EmployeeIn(BaseModel):
    name: str
    email: str
    password: str
    litellm_key: str  # enterprise agentic toolkit key assigned to this employee; write-only
    role: Role = Role.reviewer


class EmployeeUpdate(BaseModel):
    """Body for PATCH /employees/{employee_id}. Only the provided fields are changed;
    `password`/`litellm_key`, if given, replace the stored hash/encrypted key."""

    name: str | None = None
    email: str | None = None
    password: str | None = None
    litellm_key: str | None = None
    role: Role | None = None


class Employee(BaseModel):
    employee_id: str
    name: str
    email: str
    role: Role
