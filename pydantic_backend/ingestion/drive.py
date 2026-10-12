"""Google Drive helpers: create versioned project folders and upload PDF attachments."""
from __future__ import annotations

import io
from datetime import datetime
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from ..config import Settings

if TYPE_CHECKING:
    from .models import Attachment

DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive',
]

# Used when settings.drive_parent_folder_id is empty: a folder in the signed-in account's own My
# Drive (the desktop default, since another account can't reach the original shared folder).
DEFAULT_ROOT_FOLDER_NAME = 'Tender Evaluation'


class GoogleNotConnectedError(RuntimeError):
    """No Google OAuth token yet — every Drive call needs one (app.py maps this to a 503)."""


def _credentials(settings: Settings) -> Credentials:
    if not settings.gmail_token_path.exists():
        raise GoogleNotConnectedError(
            'Google Drive is not connected yet. Desktop app: set GMAIL_CLIENT_ID and '
            'GMAIL_CLIENT_SECRET in Settings (tray icon), restart, then use "Connect Gmail...". '
            'Server: run `python -m pydantic_backend.gmail_auth`.'
        )
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


def _parent_folder_id(settings: Settings) -> str:
    if settings.drive_parent_folder_id:
        return settings.drive_parent_folder_id
    return ensure_subfolder(settings, 'root', DEFAULT_ROOT_FOLDER_NAME)


def ensure_project_folder(
    settings: Settings,
    project_code: str,
    project_name: str,
    version: int,
    received_at: 'datetime',
) -> tuple[str, str, str]:
    """
    Find or create a version subfolder under the configured parent folder (see _parent_folder_id).

    Folder structure:
        <parent folder>/
            BPCL-2026-001 - Construction of XYZ Pipeline/
                Version 001 - 2026-07-18 09:30/
                Version 002 - 2026-07-19 14:05/

    Returns:
        (project_root_folder_id, version_subfolder_id, version_folder_name)
    """
    service = _drive_service(settings)
    parent_folder_id = _parent_folder_id(settings)
    proj_folder_name = _project_folder_name(project_code, project_name)
    ver_folder_name = _version_folder_name(version, received_at)

    # --- find or create project root folder ---
    q = (
        f"name = '{proj_folder_name}' "
        f"and '{parent_folder_id}' in parents "
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
            'parents': [parent_folder_id],
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


def ensure_subfolder(settings: Settings, parent_folder_id: str, name: str) -> str:
    """Find or create a subfolder `name` under `parent_folder_id`; return its id."""
    service = _drive_service(settings)
    q = (
        f"name = '{name}' "
        f"and '{parent_folder_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=q, fields='files(id,name)', spaces='drive').execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']
    meta = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id],
    }
    return service.files().create(body=meta, fields='id').execute()['id']


def download_file(settings: Settings, drive_file_id: str) -> bytes:
    """Download the raw bytes of a Drive file."""
    service = _drive_service(settings)
    buffer = io.BytesIO()
    request = service.files().get_media(fileId=drive_file_id)
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def upload_bytes(
    settings: Settings,
    name: str,
    content: bytes,
    mime_type: str,
    parent_folder_id: str,
) -> tuple[str, str]:
    """Upload raw bytes to Drive under `parent_folder_id`; return (drive_file_id, web_view_link)."""
    service = _drive_service(settings)
    meta = {'name': name, 'parents': [parent_folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    file = service.files().create(
        body=meta, media_body=media, fields='id,webViewLink'
    ).execute()
    return file['id'], file.get('webViewLink', '')
