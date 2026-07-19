"""Minimal Groq (OpenAI-compatible) chat client for detecting tender TOC sections."""
from __future__ import annotations

import json

import httpx

from ..config import Settings

_SYSTEM_PROMPT = (
    'You are reviewing the table of contents of a tender/RFP document. '
    'Identify which single TOC heading most likely introduces the "Technical Requirements / '
    'Technical Specifications / Scope of Work" section, and which single TOC heading most '
    'likely introduces the "Price / Commercial / Financial / Pricing Compliance" section. '
    'Reply with strict JSON only, in this exact shape: '
    '{"technical_heading": "<verbatim heading text or null>", '
    '"price_heading": "<verbatim heading text or null>"}. '
    'Use the heading text exactly as it appears in the TOC (drop the leading level marker if '
    'the TOC uses a "level;heading" format). If no suitable section exists, use null.'
)


async def detect_sections(settings: Settings, toc_text: str) -> tuple[str | None, str | None]:
    """Ask Groq which TOC heading covers technical requirements and which covers price. Returns (technical, price)."""
    async with httpx.AsyncClient(base_url=settings.groq_base_url, timeout=60.0) as client:
        response = await client.post(
            '/chat/completions',
            headers={'Authorization': f'Bearer {settings.groq_api_key.get_secret_value()}'},
            json={
                'model': settings.groq_model,
                'messages': [
                    {'role': 'system', 'content': _SYSTEM_PROMPT},
                    {'role': 'user', 'content': f'TOC:\n{toc_text}'},
                ],
                'temperature': 0,
                'response_format': {'type': 'json_object'},
            },
        )
        response.raise_for_status()
        body = response.json()
        content = body['choices'][0]['message']['content']
        parsed = json.loads(content)
        return parsed.get('technical_heading') or None, parsed.get('price_heading') or None
