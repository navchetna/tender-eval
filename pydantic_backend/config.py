from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra='ignore')

    gmail_client_id: str
    gmail_client_secret: SecretStr
    gmail_token_path: Path = Path('.secrets/gmail-token.json')
    gmail_query: str = 'is:unread has:attachment filename:pdf'
    database_url: SecretStr
    logfire_send: bool = False
    logfire_service_name: str = 'tender-repository-ingestion'

    # --- PDF parser (stage 2) ---
    parser_base_url: str = 'http://134.191.217.242:8069/parse-pdf-v1'
    parser_user: str = 'tender-eval'
    parser_api_key: SecretStr | None = None
    parse_poll_interval_seconds: float = 5.0
    parse_max_poll_attempts: int = 120
    parse_worker_enabled: bool = False
    parse_worker_interval_seconds: float = 30.0
    parse_batch_size: int = 5
    parse_max_attempts: int = 3

    # --- Tender/bid evaluation (stage 3) ---
    groq_api_key: SecretStr
    groq_model: str = 'llama-3.3-70b-versatile'
    groq_base_url: str = 'https://api.groq.com/openai/v1'
    reviewer_email: str = ''
    eval_batch_size: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
