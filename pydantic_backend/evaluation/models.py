"""Data models for the tender technical/price section detection + human review stage."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from ..auth.models import Role


class Topic(StrEnum):
    technical = 'technical'
    price = 'price'


class DocType(StrEnum):
    """Which document a section-detection evaluation is for."""

    tender = 'TENDER'
    bid = 'BID'


class ReviewStatus(StrEnum):
    """Lifecycle of a single topic's (technical/price) section suggestion."""

    suggested = 'SUGGESTED'  # AI proposed, awaiting human review
    approved = 'APPROVED'  # human confirmed the AI suggestion, or a correction


class PendingFile(BaseModel):
    """A PARSED file_repository row (tender or bid) that has no evaluation yet."""

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
    technical: SectionSuggestion
    price: SectionSuggestion
    model: str


class EvaluationRecord(BaseModel):
    evaluation_id: str
    file_id: str
    project_id: str
    version: int
    file_name: str | None = None
    detection_model: str | None
    technical_section_title: str | None
    technical_section_content: str | None
    technical_status: ReviewStatus
    technical_corrected: bool
    technical_reviewed_by: str | None
    technical_reviewed_at: datetime | None
    price_section_title: str | None
    price_section_content: str | None
    price_status: ReviewStatus
    price_corrected: bool
    price_reviewed_by: str | None
    price_reviewed_at: datetime | None
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
    role: Role = Role.reviewer


class EmployeeUpdate(BaseModel):
    """Body for PATCH /employees/{employee_id}. Only the provided fields are changed;
    `password`, if given, replaces the stored hash."""

    name: str | None = None
    email: str | None = None
    password: str | None = None
    role: Role | None = None


class Employee(BaseModel):
    employee_id: str
    name: str
    email: str
    role: Role
