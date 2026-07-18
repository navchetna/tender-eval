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


@lru_cache
def get_settings() -> Settings:
    return Settings()
