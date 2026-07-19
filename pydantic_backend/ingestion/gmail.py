"""Gmail OAuth and unread-PDF extraction; no files are written to disk."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..config import Settings
from .models import Attachment, IncomingEmail

GMAIL_READONLY_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive'
ALL_SCOPES = [GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE, DRIVE_SCOPE]


def authorize(settings: Settings) -> None:
    """Open the one-time local OAuth browser flow and save the refresh token outside Git."""
    settings.gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_config(
        {'installed': {'client_id': settings.gmail_client_id, 'client_secret': settings.gmail_client_secret.get_secret_value(), 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token', 'redirect_uris': ['http://localhost']}},
        scopes=ALL_SCOPES,
    )
    credentials = flow.run_local_server(port=0)
    settings.gmail_token_path.write_text(credentials.to_json(), encoding='utf-8')


def _credentials(settings: Settings) -> Credentials:
    if not settings.gmail_token_path.exists():
        raise RuntimeError('Gmail is not authorized. Run `python -m pydantic_backend.gmail_auth` first.')
    credentials = Credentials.from_authorized_user_file(settings.gmail_token_path, ALL_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        settings.gmail_token_path.write_text(credentials.to_json(), encoding='utf-8')
    if not credentials.valid:
        raise RuntimeError('Gmail token is invalid. Re-run Gmail authorization.')
    return credentials


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {item['name'].lower(): item['value'] for item in payload.get('headers', [])}


def _pdf_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for part in parts:
        result.extend(_pdf_parts(part.get('parts', [])))
        if part.get('mimeType') == 'application/pdf' and part.get('filename'):
            result.append(part)
    return result


def fetch_unread_pdf_emails(settings: Settings, max_results: int = 20) -> list[IncomingEmail]:
    service = build('gmail', 'v1', credentials=_credentials(settings), cache_discovery=False)
    listed = service.users().messages().list(userId='me', q=settings.gmail_query, maxResults=max_results).execute()
    emails: list[IncomingEmail] = []
    for item in listed.get('messages', []):
        message = service.users().messages().get(userId='me', id=item['id'], format='full').execute()
        payload = message['payload']
        attachments: list[Attachment] = []
        for part in _pdf_parts([payload]):
            attachment_id = part.get('body', {}).get('attachmentId')
            if not attachment_id:
                continue
            data = service.users().messages().attachments().get(userId='me', messageId=message['id'], id=attachment_id).execute()['data']
            attachments.append(Attachment(file_name=part['filename'], mime_type=part['mimeType'], content=base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))))
        if attachments:
            headers = _headers(payload)
            emails.append(IncomingEmail(message_id=message['id'], subject=headers.get('subject', ''), sender=headers.get('from', ''), received_at=datetime.fromtimestamp(int(message['internalDate']) / 1000, tz=timezone.utc), attachments=attachments))
    return emails


def send_email(settings: Settings, to: str, subject: str, body_text: str) -> str:
    """Send a plain-text email via the Gmail API (requires gmail.send scope); returns the sent message id."""
    from email.mime.text import MIMEText

    service = build('gmail', 'v1', credentials=_credentials(settings), cache_discovery=False)
    message = MIMEText(body_text)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    sent = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return str(sent['id'])
