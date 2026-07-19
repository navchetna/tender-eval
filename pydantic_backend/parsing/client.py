"""HTTP client for the async docling PDF parser API.

Base URL example: http://134.191.217.242:8069/parse-pdf-v1

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


class ParserClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.parser_base_url.rstrip('/')
        self._user = settings.parser_user
        headers = {}
        if settings.parser_api_key is not None:
            headers['Authorization'] = f'Bearer {settings.parser_api_key.get_secret_value()}'
        self._client = httpx.AsyncClient(headers=headers, timeout=120.0)

    async def __aenter__(self) -> 'ParserClient':
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def submit_pdf(self, file_name: str, content: bytes, mime_type: str) -> str:
        """Submit a PDF for processing; return the parser task id."""
        response = await self._client.post(
            f'{self._base}/api/convert',
            data={'user': self._user},
            files={'file': (file_name, content, mime_type or 'application/pdf')},
        )
        response.raise_for_status()
        return str(response.json()['task_id'])

    async def get_status(self, task_id: str) -> tuple[ParseStatus, str | None]:
        """Poll task state; return (status, error_message_if_any)."""
        response = await self._client.get(f'{self._base}/api/poll/{task_id}')
        response.raise_for_status()
        body = response.json()
        status = _STATUS_MAP.get(str(body.get('status', '')).lower(), ParseStatus.running)
        return status, body.get('error')

    async def fetch_markdown(self, task_id: str) -> bytes:
        response = await self._client.get(f'{self._base}/api/results/{task_id}/markdown')
        response.raise_for_status()
        return response.content

    async def fetch_tree(self, task_id: str) -> bytes:
        response = await self._client.get(f'{self._base}/api/results/{task_id}/tree')
        response.raise_for_status()
        return response.content

    async def fetch_images(self, task_id: str) -> list[tuple[str, int, bytes]]:
        """Return a list of (image_name, page, image_bytes)."""
        response = await self._client.get(f'{self._base}/api/results/{task_id}/images')
        response.raise_for_status()
        images: list[tuple[str, int, bytes]] = []
        for item in response.json().get('images', []):
            img = await self._client.get(f"{self._base}{item['url']}")
            img.raise_for_status()
            images.append((item['name'], int(item.get('page', 0)), img.content))
        return images
