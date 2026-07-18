from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FileType(StrEnum):
    tender = 'TENDER'
    bid = 'BID'
    unknown = 'UNKNOWN'


class Attachment(BaseModel):
    file_name: str
    mime_type: str
    content: bytes = Field(repr=False)


class IncomingEmail(BaseModel):
    message_id: str
    subject: str
    sender: str
    received_at: datetime
    attachments: list[Attachment]


class ProjectSubject(BaseModel):
    project_code: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    project_name: str = Field(min_length=1)


class ProjectContext(BaseModel):
    project_id: str
    project_code: str
    project_name: str
    version: int
    email_message_id: str
    drive_project_folder_id: str | None = None
    drive_version_folder_id: str | None = None
    drive_version_folder_name: str | None = None


class DriveContext(BaseModel):
    project_folder_id: str
    version_folder_id: str
    version_folder_name: str


class StoredFile(BaseModel):
    file_id: str
    file_name: str
    file_type: FileType
    processing_status: str
    drive_file_id: str | None = None
    drive_web_link: str | None = None


class StageResult(BaseModel):
    stage: str
    status: str
    detail: str | None = None


class IngestionResult(BaseModel):
    context: ProjectContext
    files: list[StoredFile]
    stages: list[StageResult]
