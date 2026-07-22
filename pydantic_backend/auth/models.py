"""Auth data models: HTTP Basic, no sessions/tokens — every request re-verifies the password."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    admin = 'ADMIN'
    reviewer = 'REVIEWER'


class CurrentUser(BaseModel):
    """The employee resolved from HTTP Basic credentials on the current request."""

    employee_id: str
    name: str
    email: str
    role: Role


class AssignReviewerRequest(BaseModel):
    """Body for POST /projects/{project_id}/assign."""

    employee_id: str
