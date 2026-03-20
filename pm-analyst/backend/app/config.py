from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = 8000

    google_api_key: Optional[str] = None
    gcp_project: Optional[str] = None
    gcp_location: str = "global"
    adk_model: str = "gemini-2.5-flash"

    # Microsoft Graph / Entra ID
    ms_client_id: Optional[str] = None
    ms_client_secret: Optional[str] = None
    ms_tenant_id: Optional[str] = None
    ms_redirect_uri: Optional[str] = None
    ms_scopes: list[str] = [
        "User.Read",
        "Calendars.Read",
        "OnlineMeetingTranscript.Read.All",
        "Files.Read",
        "Files.Read.All",
    ]

    # Frontend URL (for OAuth redirect after login)
    frontend_url: str = "http://localhost:3000"

    # Azure DevOps
    ado_org: Optional[str] = None
    ado_project: Optional[str] = None

    @model_validator(mode="after")
    def _derive_redirect_uri(self) -> "Settings":
        if self.ms_redirect_uri is None:
            self.ms_redirect_uri = (
                f"http://localhost:{self.port}/auth/microsoft/callback"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
