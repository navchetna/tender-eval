import logfire

from .config import get_settings


def configure_observability() -> None:
    settings = get_settings()
    logfire.configure(service_name=settings.logfire_service_name, send_to_logfire=settings.logfire_send)
    logfire.instrument_pydantic(record='failure')
    logfire.instrument_pydantic_ai()  # every LLM call goes through a pydantic_ai.Agent — see llm_agent.py
