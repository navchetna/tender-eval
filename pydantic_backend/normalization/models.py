"""Data models for the on-demand normalized circular-vs-submissions comparison view.

Structural field names (tender_*, bid_*, bidder) are kept from the original tender workload —
they are plumbing shared with the frontend; here "tender" = the reference circular and
"bid" = one merchant submission."""
from __future__ import annotations

from pydantic import BaseModel

from ..evaluation.models import Topic


class NormalizedRow(BaseModel):
    tender_cells: dict[str, str]  # tender's own column headers -> values, in the tender's table column order
    bid_values: dict[str, str | None]  # "<bid_label>: <field>" -> matched value (or None if no match found)
    # The heading the row's table sits under in the tender document ("Level 2:- Home screen
    # checklist"), so a section made of many small tables keeps its structure in the UI.
    tender_group: str | None = None


class NormalizedView(BaseModel):
    project_id: str
    version: int
    topic: Topic
    tender_file_name: str | None
    tender_columns: list[str]  # ordered column headers as they appear in the tender's table
    bid_columns: list[str]  # ordered "<bid_label>: <field>" column names contributed by all bids
    rows: list[NormalizedRow]


class ComplianceCell(BaseModel):
    """One merchant's LLM-judged compliance verdict for one requirement clause."""

    s: str  # ok | warn | bad | none
    t: str  # short label, e.g. "Compliant" / "Partial" / "Non-compliant" / "No response"
    x: str  # one-line summary
    full: str  # narrative rationale


class MatrixData(BaseModel):
    """Compliance matrix for a project/version: payment + service compliance rows banded
    together, each row's cells judged by an LLM from the underlying normalized comparison view."""

    project_id: str
    version: int
    bidders: list[str]  # merchant labels (field name kept for frontend plumbing compatibility)
    stale: list[str]
    rows: list[dict]  # {"band": str} band-header rows, or {"ref", "req", "cells": [ComplianceCell, ...]} data rows


class BidScore(BaseModel):
    """One merchant's holistic score for an entire section (all rows of one topic), with reasoning."""

    bidder: str  # merchant label (field name kept for frontend plumbing compatibility)
    score: int  # 0-100
    reasoning: str  # why this merchant scored this way, citing specifics from their responses


class SectionScoreResult(BaseModel):
    """LLM's independent scoring of every merchant's whole payment or service compliance
    section, plus a comparative narrative explaining why one merchant scored higher or lower
    than another. Computed fresh on request — nothing persisted."""

    project_id: str
    version: int
    topic: Topic
    scores: list[BidScore]
    comparison: str


class MerchantAssessment(BaseModel):
    """One merchant's risk assessment across both payment and service compliance sections."""

    merchant: str
    risk_level: str  # 'high' | 'medium' | 'low'
    score: int  # 0-100 compliance score, overall across whatever sections were available
    key_gaps: list[str]  # specific compliance gaps, citing clause references
    remediation_priorities: list[str]  # ordered remediation actions, most urgent first


class RiskTriageResult(BaseModel):
    """LLM's risk triage across payment + service compliance together: a per-merchant risk
    assessment plus an audit-priority ranking across all merchants ("who needs audit attention
    first"). Computed fresh on request — nothing persisted."""

    project_id: str
    version: int
    assessments: list[MerchantAssessment]
    audit_priority_order: list[str]  # every merchant exactly once, most audit-urgent first
    summary: str  # triage narrative explaining the ranking


class PromptOverride(BaseModel):
    """Optional request body for the score/triage endpoints: a blank or omitted prompt runs
    (and caches) the default; a non-blank prompt replaces the system prompt for that one
    request and is never cached, since the result is no longer a pure function of the
    approved section content alone."""

    prompt: str | None = None


class DefaultPrompts(BaseModel):
    """The default system prompts behind the Payment/Service compliance scoring and the
    cross-merchant risk triage step, so the compliance-matrix UI can show what will run
    before a reviewer chooses to override it."""

    payment: str
    service: str
    triage: str
