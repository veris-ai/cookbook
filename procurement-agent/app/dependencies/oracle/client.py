from typing import Any

import httpx

from app.dependencies.oracle.auth import OracleAuth


class OracleFusionClient:
    def __init__(self, base_url: str, auth: OracleAuth, session_id: str | None = None):
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._session_id = session_id

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            token = await self._auth.get_token(client)
            headers = kwargs.pop("headers", {})
            headers["Authorization"] = f"Bearer {token}"
            if self._session_id:
                headers["X-Veris-Session-Id"] = self._session_id

            url = f"{self._base_url}/{path}"
            resp = await client.request(method, url, headers=headers, **kwargs)

            if resp.status_code == 401:
                self._auth.invalidate()
                token = await self._auth.get_token(client)
                headers["Authorization"] = f"Bearer {token}"
                resp = await client.request(method, url, headers=headers, **kwargs)

            resp.raise_for_status()
            return resp.json()

    async def get_requisition(self, requisition_id: int) -> dict:
        return await self._request("GET", f"purchaseRequisitions/{requisition_id}")

    async def get_requisition_lines(self, requisition_id: int) -> dict:
        return await self._request("GET", f"purchaseRequisitions/{requisition_id}/child/lines")

    async def get_approved_suppliers(self) -> dict:
        return await self._request("GET", "procurementApprovedSupplierListEntries")

    async def get_supplier_contacts(self, supplier_id: int) -> dict:
        return await self._request("GET", f"suppliers/{supplier_id}/child/contacts")

    async def create_draft_po(self, body: dict) -> dict:
        return await self._request("POST", "draftPurchaseOrders", json=body)

    async def submit_draft_po(self, po_id: int) -> dict:
        return await self._request("POST", f"draftPurchaseOrders/{po_id}/action/submit")
