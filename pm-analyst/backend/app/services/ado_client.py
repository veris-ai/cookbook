"""Azure DevOps Work Item Tracking API client wrapper."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class ADOClient:
    """Thin async wrapper around Azure DevOps REST API using httpx."""

    API_VERSION = "7.1"

    def __init__(self, access_token: str, org: str, project: str):
        self._token = access_token
        self._org = org
        self._project = project
        self._base = f"https://dev.azure.com/{org}/{project}/_apis/wit"
        self._headers = {"Authorization": f"Bearer {access_token}"}
        # Temporary patch: pass simulation ID to veris mock services
        sim_id = os.environ.get("SIMULATION_ID")
        if sim_id:
            self._headers["X-Veris-Session-Id"] = sim_id
        # Log token identity for debugging
        try:
            import base64, json
            payload = access_token.split(".")[1]
            payload += "=" * (4 - len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            logger.info("ADO token identity: upn=%s, oid=%s, tid=%s",
                        claims.get("upn"), claims.get("oid"), claims.get("tid"))
        except Exception:
            pass

    async def _get(
        self, path: str, params: dict | None = None
    ) -> httpx.Response:
        params = params or {}
        params.setdefault("api-version", self.API_VERSION)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}{path}",
                headers=self._headers,
                params=params,
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp

    async def _post_patch(
        self, path: str, body: list[dict]
    ) -> httpx.Response:
        """POST with JSON Patch content type (used by ADO for creation)."""
        headers = {
            **self._headers,
            "Content-Type": "application/json-patch+json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}{path}",
                headers=headers,
                params={"api-version": self.API_VERSION},
                json=body,
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp

    async def _patch(self, path: str, body: list[dict]) -> httpx.Response:
        """PATCH with JSON Patch content type (used by ADO for updates)."""
        headers = {
            **self._headers,
            "Content-Type": "application/json-patch+json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self._base}{path}",
                headers=headers,
                params={"api-version": self.API_VERSION},
                json=body,
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp

    async def _delete(self, path: str) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self._base}{path}",
                headers=self._headers,
                params={"api-version": self.API_VERSION},
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp

    async def create_work_item(
        self,
        work_item_type: str,
        title: str,
        description: str = "",
        parent_id: int = 0,
    ) -> dict:
        """Create a work item (Epic, Feature, User Story, etc.).

        Args:
            work_item_type: e.g. "Epic", "Feature", "User Story"
            title: Work item title
            description: HTML description
            parent_id: Parent work item ID for hierarchy linking (0 = no parent)
        """
        ops: list[dict] = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": title,
            },
        ]
        if description:
            ops.append({
                "op": "add",
                "path": "/fields/System.Description",
                "value": description,
            })
        if parent_id:
            ops.append({
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": (
                        f"https://dev.azure.com/{self._org}/{self._project}"
                        f"/_apis/wit/workItems/{parent_id}"
                    ),
                },
            })

        try:
            resp = await self._post_patch(
                f"/workitems/${work_item_type}", ops
            )
        except httpx.HTTPStatusError as e:
            logger.error("ADO create_work_item failed: %s %s", e.response.status_code, e.response.text)
            raise
        return resp.json()

    async def get_work_item(self, item_id: int) -> dict:
        """Get a work item by ID with relations expanded."""
        resp = await self._get(
            f"/workitems/{item_id}", params={"$expand": "relations"}
        )
        return resp.json()

    async def update_work_item(
        self, item_id: int, ops: list[dict]
    ) -> dict:
        """Update a work item with JSON Patch operations."""
        resp = await self._patch(f"/workitems/{item_id}", ops)
        return resp.json()

    async def delete_work_item(self, item_id: int) -> dict:
        """Delete a work item (moves to recycle bin)."""
        resp = await self._delete(f"/workitems/{item_id}")
        return resp.json()

    async def query_work_items(self, wiql: str) -> dict:
        """Run a WIQL query and return matching work item references."""
        headers = {
            **self._headers,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://dev.azure.com/{self._org}/{self._project}/_apis/wit/wiql",
                headers=headers,
                params={"api-version": self.API_VERSION},
                json={"query": wiql},
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()
