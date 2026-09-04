"""HTTP client for the async docling PDF parser API.

Base URL example: https://ei-api.mg2.eglb.intel.com/pdf-pipeline

Flow:
  1. POST /api/convert            (form: user, file)   → {task_id, status}
  2. GET  /api/poll/{task_id}                          → {status: pending|done|failed, error}
  3. GET  /api/results/{task_id}/markdown              → <stem>.md
     GET  /api/results/{task_id}/tree                  → <stem>_output_tree.json
     GET  /api/results/{task_id}/images                → {images: [{name, page, url}]}
"""
from __future__ import annotations

import httpx

from ..config import Settings
from .models import ParseStatus

_STATUS_MAP = {
    'pending': ParseStatus.pending,
    'queued': ParseStatus.pending,
    'running': ParseStatus.running,
    'processing': ParseStatus.running,
    'done': ParseStatus.completed,
    'failed': ParseStatus.failed,
    'error': ParseStatus.failed,
}

# Raised when the pool hands back a socket the server has already closed: httpx sees EOF
# before any response bytes, so the request provably never reached the application and is
# always safe to replay.
_TRANSIENT_ERRORS = (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError)


class ParserClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.parser_base_url.rstrip('/')
        self._user = settings.parser_user
        headers = {}
        if settings.parser_api_key is not None and settings.parser_api_key.get_secret_value():
            headers['Authorization'] = f'Bearer {settings.parser_api_key.get_secret_value()}'
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=120.0,
            verify=settings.parser_verify_tls,
            # The parser's uvicorn drops keep-alive connections after ~5s idle, which is exactly
            # `parse_poll_interval_seconds` — so a pooled connection is almost always already dead
            # by the next poll. Opening a fresh connection per request costs nothing meaningful
            # over a local hop and removes that race entirely.
            limits=httpx.Limits(max_keepalive_connections=0),
        )

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Issue one request, retrying once if the connection dropped before a response."""
        for attempt in range(2):
            try:
                return await self._client.request(method, url, **kwargs)
            except _TRANSIENT_ERRORS:
                if attempt == 1:
                    raise
        raise RuntimeError('unreachable')

    async def __aenter__(self) -> 'ParserClient':
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def submit_pdf(self, file_name: str, content: bytes, mime_type: str) -> str:
        """Submit a PDF for processing; return the parser task id."""
        response = await self._request(
            'POST',
            f'{self._base}/api/convert',
            data={'user': self._user},
            files={'file': (file_name, content, mime_type or 'application/pdf')},
        )
        response.raise_for_status()
        return str(response.json()['task_id'])

    async def get_status(self, task_id: str) -> tuple[ParseStatus, str | None]:
        """Poll task state; return (status, error_message_if_any)."""
        response = await self._request('GET', f'{self._base}/api/poll/{task_id}')
        response.raise_for_status()
        body = response.json()
        status = _STATUS_MAP.get(str(body.get('status', '')).lower(), ParseStatus.running)
        return status, body.get('error')

    async def fetch_markdown(self, task_id: str) -> bytes:
        response = await self._request('GET', f'{self._base}/api/results/{task_id}/markdown')
        response.raise_for_status()
        return response.content

    async def fetch_tree(self, task_id: str) -> bytes:
        response = await self._request('GET', f'{self._base}/api/results/{task_id}/tree')
        response.raise_for_status()
        return response.content

    async def fetch_toc(self, task_id: str) -> bytes | None:
        """Return TOC bytes, or None if the parser does not expose a /toc endpoint."""
        response = await self._request('GET', f'{self._base}/api/results/{task_id}/toc')
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.content

    async def fetch_images(self, task_id: str) -> list[tuple[str, int, bytes]]:
        """Return a list of (image_name, page, image_bytes)."""
        response = await self._request('GET', f'{self._base}/api/results/{task_id}/images')
        response.raise_for_status()
        images: list[tuple[str, int, bytes]] = []
        for item in response.json().get('images', []):
            img = await self._request('GET', f"{self._base}{item['url']}")
            img.raise_for_status()
            images.append((item['name'], int(item.get('page', 0)), img.content))
        return images
