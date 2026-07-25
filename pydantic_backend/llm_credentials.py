"""
Per-employee LiteLLM gateway credentials (enterprise agentic toolkit), replacing the single
shared LLM key. Each employee's key is stored encrypted at rest; the caller's own key is
resolved per-request (see auth/dependencies.py::get_llm_credentials) and threaded through the
evaluation/normalization clients instead of a global API key.
"""
from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet

from .config import Settings


@dataclass
class LlmCredentials:
    """What a single LLM chat-completion call needs: whose key, and where/what model to hit."""

    api_key: str
    base_url: str
    model: str
    verify_tls: bool = True


def _fernet(settings: Settings) -> Fernet:
    return Fernet(settings.litellm_key_encryption_key.get_secret_value().encode('utf-8'))


def encrypt_key(plaintext: str, settings: Settings) -> str:
    return _fernet(settings).encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_key(ciphertext: str, settings: Settings) -> str:
    return _fernet(settings).decrypt(ciphertext.encode('utf-8')).decode('utf-8')


def worker_llm_credentials(settings: Settings) -> LlmCredentials:
    """Credentials for the unattended background pipeline worker — it has no logged-in
    employee to pull a key from, so it uses its own dedicated key instead."""
    return LlmCredentials(
        api_key=settings.litellm_worker_api_key.get_secret_value(),
        base_url=settings.litellm_base_url,
        model=settings.litellm_model,
        verify_tls=settings.litellm_verify_tls,
    )
