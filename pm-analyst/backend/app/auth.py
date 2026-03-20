"""Microsoft OAuth2 authentication routes."""

import base64
import json
import logging
import secrets
import time

import httpx
import msal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/microsoft", tags=["auth"])

# In-memory token store: session_token -> {ms_access_token, ado_access_token, ...}
_token_store: dict[str, dict] = {}


def _build_msal_app() -> msal.ConfidentialClientApplication:
    settings = get_settings()
    if not settings.ms_client_id or not settings.ms_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Microsoft client ID and secret are not configured",
        )
    authority = f"https://login.microsoftonline.com/{settings.ms_tenant_id or 'common'}"
    return msal.ConfidentialClientApplication(
        client_id=settings.ms_client_id,
        client_credential=settings.ms_client_secret,
        authority=authority,
        validate_authority=False,
    )


def _extract_tenant_from_token(access_token: str) -> str | None:
    """Extract the tenant ID from a JWT access token without validation."""
    try:
        payload = access_token.split(".")[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("tid")
    except Exception:
        return None


async def _exchange_refresh_for_ado_token(refresh_token: str, tenant: str | None = None) -> str | None:
    """Use a refresh token to get an ADO-scoped access token via token endpoint."""
    settings = get_settings()
    if not settings.ms_client_id or not settings.ms_client_secret:
        return None

    tenant = tenant or settings.ms_tenant_id or "common"
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.ms_client_id,
                "client_secret": settings.ms_client_secret,
                "refresh_token": refresh_token,
                "scope": "499b84ac-1321-427f-aa17-267ca6975798/user_impersonation offline_access",
            },
            timeout=30.0,
        )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token")
    logger.warning("Failed to get ADO token: %s %s", resp.status_code, resp.text)
    return None


@router.get("/login")
async def login(request: Request):
    """Redirect user to Microsoft login (Graph scopes only)."""
    settings = get_settings()
    app = _build_msal_app()
    auth_url = app.get_authorization_request_url(
        scopes=settings.ms_scopes,
        redirect_uri=settings.ms_redirect_uri,
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(request: Request, code: str | None = None, error: str | None = None):
    """Handle OAuth callback from Microsoft."""
    if error:
        raise HTTPException(status_code=400, detail=f"Auth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    settings = get_settings()
    app = _build_msal_app()

    # Redeem auth code for Graph token
    graph_result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=settings.ms_scopes,
        redirect_uri=settings.ms_redirect_uri,
    )

    if "error" in graph_result:
        raise HTTPException(
            status_code=400,
            detail=f"Token error: {graph_result.get('error_description', graph_result['error'])}",
        )

    # Use refresh token to get a separate ADO-scoped token
    ado_access_token = None
    refresh_token = graph_result.get("refresh_token")
    user_tenant = _extract_tenant_from_token(graph_result["access_token"])
    logger.info("User tenant from token: %s", user_tenant)
    if refresh_token and settings.ado_org:
        ado_access_token = await _exchange_refresh_for_ado_token(refresh_token, user_tenant)
        if ado_access_token:
            logger.info("ADO token acquired via refresh token exchange")
        else:
            logger.warning("Could not acquire ADO token")

    session_token = secrets.token_urlsafe(32)
    _token_store[session_token] = {
        "ms_access_token": graph_result["access_token"],
        "ado_access_token": ado_access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + graph_result.get("expires_in", 3600),
    }

    logger.info("Microsoft auth completed, session token issued")
    frontend_url = settings.frontend_url.rstrip("/")
    return RedirectResponse(
        url=f"{frontend_url}/auth/callback?session_token={session_token}"
    )


@router.get("/status")
async def status(token: str | None = None):
    """Check if a session token is valid and authenticated."""
    if not token or token not in _token_store:
        return {"authenticated": False}

    entry = _token_store[token]
    expired = time.time() > entry["expires_at"]
    return {"authenticated": not expired}


def get_tokens(session_token: str) -> dict | None:
    """Look up both Graph and ADO tokens by session token."""
    entry = _token_store.get(session_token)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        return None
    return {
        "ms_access_token": entry["ms_access_token"],
        "ado_access_token": entry.get("ado_access_token"),
    }
