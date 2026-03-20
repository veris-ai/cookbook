"""Test script for mock Oracle Fusion Cloud service.

Start the mock first:
  cd veris_sandbox/services/oracle && uv run uvicorn app.main:app --port 8010

Then run:
  uv run python test_oracle_mock.py
"""

import asyncio
import json

import httpx

BASE = "http://localhost:8010"
API = f"{BASE}/fscmRestApi/resources/11.13.18.05"
SESSION = "test-1"


async def main():
    async with httpx.AsyncClient(timeout=30.0) as c:
        print("=== 1. Health check ===")
        r = await c.get(f"{BASE}/health")
        print(json.dumps(r.json(), indent=2))

        print("\n=== 2. OAuth token ===")
        r = await c.post(f"{BASE}/oauth2/v1/token", data={
            "grant_type": "client_credentials",
            "client_id": "mock-client-id",
            "client_secret": "mock-client-secret",
        })
        token = r.json()["access_token"]
        print(f"Token: {token}")
        headers = {"Authorization": f"Bearer {token}", "X-Veris-Session-Id": SESSION}

        print("\n=== 3. Seed (LLM generates data) ===")
        r = await c.post(f"{BASE}/seed", json={
            "session_id": SESSION,
            "seed_instruction": "500 business laptops for new Seattle office, Q3 delivery, budget $600k. 3 suppliers: Dell, Lenovo, HP.",
        })
        print(json.dumps(r.json(), indent=2))

        print("\n=== 4. GET approved suppliers ===")
        r = await c.get(f"{API}/procurementApprovedSupplierListEntries", headers=headers, params={"session_id": SESSION})
        asl = r.json()
        print(json.dumps(asl, indent=2))

        print("\n=== 5. GET requisitions (list) ===")
        r = await c.get(f"{API}/purchaseRequisitions", headers=headers, params={"session_id": SESSION})
        reqs = r.json()
        print(json.dumps(reqs, indent=2))

        req_id = None
        if "items" in reqs and reqs["items"]:
            req_id = reqs["items"][0].get("RequisitionHeaderId")
        elif "RequisitionHeaderId" in reqs:
            req_id = reqs["RequisitionHeaderId"]

        if req_id:
            print(f"\n=== 6. GET requisition {req_id} ===")
            r = await c.get(f"{API}/purchaseRequisitions/{req_id}", headers=headers, params={"session_id": SESSION})
            req = r.json()
            print(json.dumps(req, indent=2))

            print(f"\n=== 7. GET requisition {req_id} lines ===")
            r = await c.get(f"{API}/purchaseRequisitions/{req_id}/child/lines", headers=headers, params={"session_id": SESSION})
            print(json.dumps(r.json(), indent=2))
        else:
            print("\n!!! Could not extract RequisitionHeaderId from response")

        supplier_id = None
        if "items" in asl and asl["items"]:
            supplier_id = asl["items"][0].get("SupplierId")

        if supplier_id:
            print(f"\n=== 8. GET supplier {supplier_id} contacts ===")
            r = await c.get(f"{API}/suppliers/{supplier_id}/child/contacts", headers=headers, params={"session_id": SESSION})
            print(json.dumps(r.json(), indent=2))
        else:
            print("\n!!! Could not extract SupplierId from ASL response")

        print("\n=== 9. POST create draft PO ===")
        po_body = {
            "BuyerId": 100000012346,
            "DocumentStyleId": 1,
            "ProcurementBUId": 204,
            "SupplierId": supplier_id or 1001,
            "Supplier": "Dell Technologies",
            "CurrencyCode": "USD",
            "Description": "500 Business Laptops - Seattle Office",
            "lines": [{
                "LineNumber": 1,
                "LineType": "Goods",
                "LineTypeId": 1,
                "Description": "Business Laptop - 16GB RAM, 512GB SSD",
                "Quantity": 500,
                "Price": 1050.00,
                "UOMCode": "Ea",
                "UOM": "Each",
            }],
        }
        r = await c.post(f"{API}/draftPurchaseOrders", headers=headers, params={"session_id": SESSION}, json=po_body)
        draft_po = r.json()
        print(json.dumps(draft_po, indent=2))

        po_header_id = draft_po.get("POHeaderId")
        if po_header_id:
            print(f"\n=== 10. POST submit draft PO {po_header_id} ===")
            r = await c.post(
                f"{API}/draftPurchaseOrders/{po_header_id}/action/submit",
                headers=headers,
                params={"session_id": SESSION},
            )
            print(json.dumps(r.json(), indent=2))
        else:
            print("\n!!! Could not extract POHeaderId from draft PO response")

        print("\n=== 11. GET purchase orders (read-only view) ===")
        r = await c.get(f"{API}/purchaseOrders", headers=headers, params={"session_id": SESSION})
        print(json.dumps(r.json(), indent=2))

        print("\n=== Done ===")


asyncio.run(main())
