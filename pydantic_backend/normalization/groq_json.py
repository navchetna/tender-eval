"""Shared JSON-mode Groq chat-completion call, with a retry for reasoning-model JSON truncation."""
from __future__ import annotations

import json

import httpx

from ..config import Settings


async def call_json(settings: Settings, system_prompt: str, user_prompt: str, *, attempts: int = 2) -> dict:
    payload = {
        'model': settings.groq_model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        # Reasoning models (e.g. gpt-oss) spend tokens on hidden reasoning before the JSON body;
        # a whole-section prompt (multiple bidders, many rows) needs enough budget that the
        # reasoning doesn't crowd out the actual answer and truncate it into invalid JSON.
        'max_completion_tokens': 4096,
        'reasoning_effort': 'low',
    }

    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            async with httpx.AsyncClient(base_url=settings.groq_base_url, timeout=90.0) as client:
                response = await client.post(
                    '/chat/completions',
                    headers={'Authorization': f'Bearer {settings.groq_api_key.get_secret_value()}'},
                    json=payload,
                )
                response.raise_for_status()
                return json.loads(response.json()['choices'][0]['message']['content'])
        except (httpx.HTTPStatusError, json.JSONDecodeError, KeyError, IndexError) as exc:
            last_error = exc
            continue
    raise last_error  # noqa: RSE102 — surfaced as-is; caller turns it into a clear error
