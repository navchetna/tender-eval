from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    # --- PDF parser (stage 2): local LightOnOCR (GPU) service, docling-compatible /api/convert contract ---
    parser_base_url: str = 'http://host.docker.internal:8010'
    parser_user: str = 'tender-bid'
    parser_verify_tls: bool = False
    parser_api_key: SecretStr | None = None
    parse_poll_interval_seconds: float = 5.0
    parse_max_poll_attempts: int = 120
    parse_worker_enabled: bool = False
    parse_worker_interval_seconds: float = 30.0
    parse_batch_size: int = 5
    parse_max_attempts: int = 3

    # --- Tender/bid evaluation (stage 3): local LiteLLM proxy, fronting NPU-served Qwen3
    # (fast: extraction/matching/drafting) and Claude (quality: judgment/scoring/comparison) ---
    litellm_base_url: str = 'http://litellm:4000'
    litellm_master_key: SecretStr = SecretStr('')
    litellm_fast_model: str = 'npu-qwen3-4b'
    litellm_quality_model: str = 'claude-eval'
    litellm_verify_tls: bool = False
    reviewer_email: str = ''
    eval_batch_size: int = 5

    # --- Model runtime. 'litellm' (the Docker/WSL deployment) sends every model call over HTTP:
    # OCR to the docling parser service, fast/quality calls to the LiteLLM proxy. 'inprocess' (the
    # desktop .exe, see desktop/) loads the on-device models straight into this process with
    # OpenVINO GenAI — no OVMS, llama.cpp, parser service or LiteLLM — and calls Anthropic
    # directly for the quality tier. Models download from Hugging Face into models_dir on first
    # use; device-specific compiled blobs are cached in ov_cache_dir. ---
    model_runtime: Literal['litellm', 'inprocess'] = 'litellm'
    models_dir: Path = Path('models')
    ov_cache_dir: Path = Path('ov_cache')
    local_fast_model_repo: str = 'ervin0307/Qwen3-4B-Instruct-2507-int4-ov'
    local_fast_model_device: str = 'NPU'
    # NPU compiles static shapes: prompts longer than this are rejected, and raising it costs
    # compile time + memory. Ignored on CPU/GPU.
    local_fast_model_max_prompt_len: int = 8192
    local_fast_model_max_new_tokens: int = 2048
    local_ocr_model_repo: str = 'ervin0307/LightOnOCR-3-0.8B-int8-ov'
    local_ocr_model_device: str = 'GPU'
    local_ocr_max_new_tokens: int = 4096
    anthropic_api_key: SecretStr = SecretStr('')
    anthropic_quality_model: str = 'claude-sonnet-4-5'

    # --- Auth (stage 4): HTTP Basic, bootstrapped admin account ---
    admin_email: str = ''
    admin_password: SecretStr = SecretStr('')

    # --- CORS (stage 5): browser origins allowed to call this API directly ---
    cors_origins: list[str] = ['http://localhost:3000']


@lru_cache
def get_settings() -> Settings:
    return Settings()
