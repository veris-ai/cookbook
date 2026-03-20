import httpx


class OracleAuth:
    def __init__(self, token_url: str, client_id: str, client_secret: str):
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None

    async def get_token(self, client: httpx.AsyncClient) -> str:
        if self._access_token is None:
            await self._refresh(client)
        return self._access_token

    async def _refresh(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]

    def invalidate(self) -> None:
        self._access_token = None
