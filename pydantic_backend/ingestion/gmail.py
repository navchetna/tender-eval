"""Gmail OAuth and unread-PDF extraction; no files are written to disk."""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build

from ..config import Settings
from .models import Attachment, IncomingEmail

GMAIL_READONLY_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive'
ALL_SCOPES = [GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE, DRIVE_SCOPE]

# Google may return the granted scopes in a different order/format than requested; without this,
# oauthlib treats that as "scope has changed" and fails the token exchange.
os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')


def _client_config(settings: Settings) -> dict:
    return {'installed': {'client_id': settings.gmail_client_id, 'client_secret': settings.gmail_client_secret.get_secret_value(), 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token', 'redirect_uris': ['http://localhost']}}


def authorize(settings: Settings) -> None:
    """Open the one-time local OAuth browser flow and save the refresh token outside Git."""
    settings.gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_config(_client_config(settings), scopes=ALL_SCOPES)
    credentials = flow.run_local_server(port=0)
    settings.gmail_token_path.write_text(credentials.to_json(), encoding='utf-8')


# --- In-app sign-in: the UI's "Connect Google" button (no script, no restart) -----------------
# Google's "Desktop app" OAuth clients accept any loopback redirect (http://127.0.0.1:<port>/<path>
# or http://localhost...), so the app's own callback endpoint can receive the code directly.
# A started-but-unfinished sign-in, keyed by OAuth `state`: (flow, where to send the browser after).
_pending_web_flows: dict[str, tuple[Flow, str]] = {}


class GoogleSignInError(RuntimeError):
    pass


def start_web_authorization(settings: Settings, redirect_uri: str, return_to: str) -> str:
    """Begin the browser sign-in; returns Google's consent URL to send the user to."""
    if not settings.gmail_client_id or not settings.gmail_client_secret.get_secret_value():
        raise GoogleSignInError(
            'Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET first (Start menu > Tender Evaluation '
            'settings), then restart the app.'
        )
    # Loopback only: that's all a Desktop-app OAuth client accepts anyway, and it keeps the
    # unauthenticated callback from redirecting the browser anywhere but back to this app.
    if any(urlsplit(url).hostname not in ('127.0.0.1', 'localhost') for url in (redirect_uri, return_to)):
        raise GoogleSignInError('Google sign-in from the app only works on this computer (127.0.0.1/localhost).')
    flow = Flow.from_client_config(_client_config(settings), scopes=ALL_SCOPES, redirect_uri=redirect_uri)
    # access_type=offline + prompt=consent: always return a refresh token, so the connection
    # keeps working after the first hour without signing in again.
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    _pending_web_flows[state] = (flow, return_to)
    return auth_url


def finish_web_authorization(settings: Settings, state: str, code: str) -> str:
    """Exchange the code Google redirected back with for a token and save it. Returns the URL to
    send the browser back to. Blocking (one HTTPS call to Google)."""
    pending = _pending_web_flows.pop(state, None)
    if pending is None:
        raise GoogleSignInError('This sign-in link has expired. Click "Connect Google" in the app again.')
    flow, return_to = pending
    flow.fetch_token(code=code)
    settings.gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
    settings.gmail_token_path.write_text(flow.credentials.to_json(), encoding='utf-8')
    return return_to


def _credentials(settings: Settings) -> Credentials:
    if not settings.gmail_token_path.exists():
        raise RuntimeError('Google is not connected. Use "Connect Google" on the Projects page.')
    credentials = Credentials.from_authorized_user_file(settings.gmail_token_path, ALL_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        settings.gmail_token_path.write_text(credentials.to_json(), encoding='utf-8')
    if not credentials.valid:
        raise RuntimeError('Gmail token is invalid. Re-run Gmail authorization.')
    return credentials


def is_authorized(settings: Settings) -> bool:
    """Re-checks the token file on disk each call, so this reflects a token dropped into a
    running pod (e.g. via `kubectl cp`) without needing a backend restart."""
    try:
        _credentials(settings)
        return True
    except RuntimeError:
        return False


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
