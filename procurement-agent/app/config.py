from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    email_backend: Literal["agentmail", "gmail"] = "agentmail"

    # Common email settings
    email_inbox_id: str | None = None
    email_poll_interval: int = 5
    email_webhook_url: str | None = None

    # AgentMail-specific
    agentmail_api_key: str | None = None

    oracle_base_url: str = "https://efao.fa.us6.oraclecloud.com/fscmRestApi/resources/11.13.18.05"
    oracle_token_url: str = "https://efao.fa.us6.oraclecloud.com/oauth2/v1/token"
    oracle_client_id: str = "mock-client-id"
    oracle_client_secret: str = "mock-client-secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_backend_config(self) -> "Settings":
        if not self.email_inbox_id:
            raise ValueError("EMAIL_INBOX_ID is required")
        if self.email_backend == "agentmail" and not self.agentmail_api_key:
            raise ValueError("AGENTMAIL_API_KEY required when EMAIL_BACKEND=agentmail")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
