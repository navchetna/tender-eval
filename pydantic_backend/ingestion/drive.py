"""Google Drive helpers: create versioned project folders and upload PDF attachments."""
from __future__ import annotations

import io
from datetime import datetime
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from ..config import Settings

if TYPE_CHECKING:
    from .models import Attachment

DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive',
]

PARENT_FOLDER_ID = '153OSg8o20lRxEU4sYpipZgochPXj50yL'


def _credentials(settings: Settings) -> Credentials:
    credentials = Credentials.from_authorized_user_file(
        settings.gmail_token_path, DRIVE_SCOPES
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        settings.gmail_token_path.write_text(credentials.to_json(), encoding='utf-8')
    if not credentials.valid:
        raise RuntimeError('OAuth token is invalid. Re-run authorization.')
    return credentials


def _drive_service(settings: Settings):
    return build('drive', 'v3', credentials=_credentials(settings), cache_discovery=False)


def _project_folder_name(project_code: str, project_name: str) -> str:
    return f'{project_code} - {project_name}'


def _version_folder_name(version: int, received_at: 'datetime') -> str:
    dt_str = received_at.strftime('%Y-%m-%d %H:%M')
    return f'Version {version:03d} - {dt_str}'


def ensure_project_folder(
    settings: Settings,
    project_code: str,
    project_name: str,
    version: int,
    received_at: 'datetime',
) -> tuple[str, str, str]:
    """
    Find or create a version subfolder under PARENT_FOLDER_ID.

    Folder structure:
        <PARENT_FOLDER_ID>/
            BPCL-2026-001 - Construction of XYZ Pipeline/
                Version 001 - 2026-07-18 09:30/
                Version 002 - 2026-07-19 14:05/

    Returns:
        (project_root_folder_id, version_subfolder_id, version_folder_name)
    """
    service = _drive_service(settings)
    proj_folder_name = _project_folder_name(project_code, project_name)
    ver_folder_name = _version_folder_name(version, received_at)

    # --- find or create project root folder ---
    q = (
        f"name = '{proj_folder_name}' "
        f"and '{PARENT_FOLDER_ID}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=q, fields='files(id,name)', spaces='drive').execute()
    folders = results.get('files', [])

    if folders:
        project_folder_id = folders[0]['id']
    else:
        meta = {
            'name': proj_folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [PARENT_FOLDER_ID],
        }
        project_folder_id = service.files().create(body=meta, fields='id').execute()['id']

    # --- create version subfolder (always new per ingestion) ---
    meta = {
        'name': ver_folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [project_folder_id],
    }
    version_folder_id = service.files().create(body=meta, fields='id').execute()['id']

    return project_folder_id, version_folder_id, ver_folder_name


def upload_attachment(
    settings: Settings,
    attachment: 'Attachment',
    parent_folder_id: str,
) -> tuple[str, str]:
    """
    Upload a PDF attachment to Drive.

    Returns:
        (drive_file_id, web_view_link)
    """
    service = _drive_service(settings)
    meta = {'name': attachment.file_name, 'parents': [parent_folder_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(attachment.content),
        mimetype=attachment.mime_type,
        resumable=False,
    )
    file = service.files().create(
        body=meta, media_body=media, fields='id,webViewLink'
    ).execute()
    return file['id'], file.get('webViewLink', '')
