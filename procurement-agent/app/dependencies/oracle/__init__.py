from app.config import get_settings
from app.dependencies.oracle.auth import OracleAuth
from app.dependencies.oracle.client import OracleFusionClient

_auth: OracleAuth | None = None


def get_oracle_client(session_id: str | None = None) -> OracleFusionClient:
    global _auth
    if _auth is None:
        settings = get_settings()
        _auth = OracleAuth(
            settings.oracle_token_url,
            settings.oracle_client_id,
            settings.oracle_client_secret,
        )
    settings = get_settings()
    return OracleFusionClient(settings.oracle_base_url, _auth, session_id)
