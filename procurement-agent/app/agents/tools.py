import asyncio
import json
from typing import Any

from agents import RunContextWrapper, function_tool

from app.agents.context import ProcurementContext
from app.config import get_settings
from app.dependencies.oracle import get_oracle_client
from app.email import get_email_client

_quotes: dict[str, dict[str, Any]] = {}
_TRACKED_FIELDS = ["unit_price", "total_price", "timeline", "scope", "terms", "warranty", "delivery_date"]


@function_tool
async def oracle_connector(
    ctx: RunContextWrapper[ProcurementContext],
    action: str,
    requisition_id: int | None = None,
    supplier_id: int | None = None,
    po_id: int | None = None,
    po_body: str | None = None,
) -> dict[str, Any]:
    """Interface to Oracle Fusion Cloud Procurement REST API.

    Actions:
    - read_requisition: Get a purchase requisition. Requires requisition_id.
    - get_requisition_lines: Get line items for a requisition. Requires requisition_id.
    - get_approved_suppliers: List all approved supplier list entries.
    - get_supplier_contacts: Get contacts for a supplier. Requires supplier_id.
    - create_draft_po: Create a draft purchase order. Requires po_body as a JSON string with BuyerId, DocumentStyleId, ProcurementBUId, SupplierId, lines[], etc.
    - submit_draft_po: Submit a draft PO for approval. Requires po_id.
    """
    client = get_oracle_client()

    match action:
        case "read_requisition":
            result = await client.get_requisition(requisition_id)
            budget = result.get("BudgetAmount") or result.get("Amount") or 0
            if budget and ctx.context.budget_ceiling == 0:
                ctx.context.budget_ceiling = float(budget)
            if requisition_id and not ctx.context.requisition_id:
                ctx.context.requisition_id = requisition_id
            return result
        case "get_requisition_lines":
            return await client.get_requisition_lines(requisition_id)
        case "get_approved_suppliers":
            result = await client.get_approved_suppliers()
            ctx.context.approved_suppliers = result.get("items", [])
            return result
        case "get_supplier_contacts":
            return await client.get_supplier_contacts(supplier_id)
        case "create_draft_po":
            return await client.create_draft_po(json.loads(po_body))
        case "submit_draft_po":
            return await client.submit_draft_po(po_id)
        case _:
            raise ValueError(f"Unknown oracle_connector action: {action}")


@function_tool
async def quote_tracker(
    action: str,
    vendor_name: str,
    unit_price: float | None = None,
    total_price: float | None = None,
    timeline: str | None = None,
    scope: str | None = None,
    terms: str | None = None,
    warranty: str | None = None,
    delivery_date: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Track and compare vendor quotes during procurement negotiation.

    Actions:
    - store: Save or update a vendor's quote. Requires vendor_name plus quote fields. Overwrites any existing quote for that vendor. Returns stored data and flags missing fields.
    - compare: Compare all stored quotes side-by-side. Returns quotes ranked by total_price and missing fields per vendor. vendor_name is ignored.
    - get: Retrieve a specific vendor's stored quote. Requires vendor_name.
    """
    match action:
        case "store":
            quote = {
                k: v
                for k, v in {
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "timeline": timeline,
                    "scope": scope,
                    "terms": terms,
                    "warranty": warranty,
                    "delivery_date": delivery_date,
                    "notes": notes,
                }.items()
                if v is not None
            }
            _quotes[vendor_name] = quote
            missing = [f for f in _TRACKED_FIELDS if f not in quote]
            return {"status": "stored", "vendor": vendor_name, "quote": quote, "missing_fields": missing}

        case "compare":
            ranking = sorted(
                _quotes.keys(),
                key=lambda v: _quotes[v].get("total_price", float("inf")),
            )
            missing_by_vendor = {
                v: [f for f in _TRACKED_FIELDS if f not in _quotes[v]]
                for v in _quotes
            }
            return {
                "quotes": _quotes,
                "ranking_by_total_price": ranking,
                "missing_fields": missing_by_vendor,
                "total_quotes": len(_quotes),
            }

        case "get":
            quote = _quotes.get(vendor_name)
            if quote is None:
                return {"status": "not_found", "vendor": vendor_name}
            return {"vendor": vendor_name, "quote": quote}

        case _:
            raise ValueError(f"Unknown quote_tracker action: {action}")


@function_tool
async def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
    """Send an email from the procurement agent's inbox.

    Use this to send RFQ emails to vendors, follow-up messages, or notifications.
    Do NOT use this for your main reply — that is handled automatically via your output.
    """
    client = get_email_client()
    result = await asyncio.to_thread(client.send_message, to=to, subject=subject, body=body)
    return {"status": "sent", "message_id": result["message_id"], "thread_id": result["thread_id"]}
