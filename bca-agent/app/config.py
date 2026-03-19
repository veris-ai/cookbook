from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google ADK / Vertex AI
    google_api_key: Optional[str] = None
    gcp_project: Optional[str] = None
    gcp_location: str = "global"  # Location for LLM calls
    gcp_service_account_json: Optional[str] = None  # SA key JSON as a string (alternative to GOOGLE_APPLICATION_CREDENTIALS file)
    adk_model: str = "gemini-2.5-flash"

    # Vertex AI RAG (can be in a different region than the LLM)
    rag_corpus_id: Optional[str] = None
    rag_location: str = "europe-west4"

    # Hogan API
    hogan_api_base_url: str = "http://localhost:8080"
    hogan_api_username: Optional[str] = None
    hogan_api_password: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def rag_corpus_resource(self) -> Optional[str]:
        """Full resource name for the RAG corpus."""
        if self.rag_corpus_id and self.gcp_project:
            return f"projects/{self.gcp_project}/locations/{self.rag_location}/ragCorpora/{self.rag_corpus_id}"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
