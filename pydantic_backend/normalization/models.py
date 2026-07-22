"""Data models for the on-demand normalized tender-vs-bid comparison view."""
from __future__ import annotations

from pydantic import BaseModel

from ..evaluation.models import Topic


class NormalizedRow(BaseModel):
    tender_cells: dict[str, str]  # tender's own column headers -> values, in the tender's table column order
    bid_values: dict[str, str | None]  # "<bid_label>: <field>" -> matched value (or None if no match found)


class NormalizedView(BaseModel):
    project_id: str
    version: int
    topic: Topic
    tender_file_name: str | None
    tender_columns: list[str]  # ordered column headers as they appear in the tender's table
    bid_columns: list[str]  # ordered "<bid_label>: <field>" column names contributed by all bids
    rows: list[NormalizedRow]


class ComplianceCell(BaseModel):
    """One bidder's LLM-judged compliance verdict for one requirement row."""

    s: str  # ok | warn | bad | none
    t: str  # short label, e.g. "Compliant" / "Partial" / "Non-compliant" / "No response"
    x: str  # one-line summary
    full: str  # narrative rationale


class MatrixData(BaseModel):
    """Compliance matrix for a project/version: technical + price rows banded together,
    each row's cells judged by an LLM from the underlying normalized comparison view."""

    project_id: str
    version: int
    bidders: list[str]
    stale: list[str]
    rows: list[dict]  # {"band": str} band-header rows, or {"ref", "req", "cells": [ComplianceCell, ...]} data rows


class BidScore(BaseModel):
    """One bidder's holistic score for an entire section (all rows of one topic), with reasoning."""

    bidder: str
    score: int  # 0-100
    reasoning: str  # why this bidder scored this way, citing specifics from their responses


class SectionScoreResult(BaseModel):
    """LLM's independent scoring of every bidder's whole technical or price section, plus a
    comparative narrative explaining why one bidder scored higher or lower than another.
    Computed fresh on request — nothing persisted."""

    project_id: str
    version: int
    topic: Topic
    scores: list[BidScore]
    comparison: str


class BidAssessment(BaseModel):
    """One bidder's extended overall assessment across both technical and price sections."""

    bidder: str
    score: int  # 0-100, overall across whatever sections were available
    pros: list[str]
    cons: list[str]
    precautions: list[str]  # risks/caveats to watch before awarding to this bidder


class ComparisonResult(BaseModel):
    """LLM's detailed overall comparison across technical + price together: an extended
    pros/cons/precautions assessment per bidder plus one overall recommendation. Computed
    fresh on request — nothing persisted."""

    project_id: str
    version: int
    assessments: list[BidAssessment]
    recommended_bidder: str | None
    recommendation: str
