"""Full 5-turn procurement workflow test: sourcing → negotiation × 3 → finalization."""

import asyncio
import json

from dotenv import load_dotenv
load_dotenv()

from agents import Agent, Runner, function_tool, set_default_openai_key
from app.agents.tools import oracle_connector, quote_tracker, send_email, _quotes
from app.agents.policy_checker import check_policy
from app.config import get_settings
from pydantic import BaseModel

set_default_openai_key(get_settings().openai_api_key)


class EmailReply(BaseModel):
    to: str
    subject: str
    body: str
    in_reply_to: str | None = None


INSTRUCTION = open("app/agents/instruction.md").read()

sent_emails = []
oracle_calls = []

def mock_send_email(to: str, subject: str, body: str) -> dict:
    sent_emails.append({"to": to, "subject": subject, "body": body[:200]})
    return {"status": "sent", "message_id": f"mock-{len(sent_emails)}", "thread_id": "mock-thread"}

mock_send_tool = function_tool(mock_send_email)
mock_send_tool.name = "send_email"
mock_send_tool.description = send_email.description

mock_oracle_data = {
    "get_approved_suppliers": {
        "items": [
            {"SupplierListEntryId": 1, "SupplierId": 100, "Supplier": "Dell Technologies", "Status": "ACTIVE"},
            {"SupplierListEntryId": 2, "SupplierId": 200, "Supplier": "Lenovo", "Status": "ACTIVE"},
            {"SupplierListEntryId": 3, "SupplierId": 300, "Supplier": "HP Inc", "Status": "ACTIVE"},
        ]
    },
    "get_supplier_contacts_100": {
        "items": [{"ContactId": 1, "ContactName": "Sarah Johnson", "Email": "sarah@dell.test"}]
    },
    "get_supplier_contacts_200": {
        "items": [{"ContactId": 2, "ContactName": "Mike Chen", "Email": "mike@lenovo.test"}]
    },
    "get_supplier_contacts_300": {
        "items": [{"ContactId": 3, "ContactName": "Lisa Park", "Email": "lisa@hp.test"}]
    },
}

async def mock_oracle(action: str, requisition_id: int | None = None, supplier_id: int | None = None, po_id: int | None = None, po_body: str | None = None):
    oracle_calls.append({"action": action, "supplier_id": supplier_id, "po_id": po_id, "po_body": po_body})
    if action == "get_approved_suppliers":
        return mock_oracle_data["get_approved_suppliers"]
    if action == "get_supplier_contacts":
        return mock_oracle_data[f"get_supplier_contacts_{supplier_id}"]
    if action == "create_draft_po":
        return {"PurchaseOrderId": 9001, "OrderNumber": "PO-9001", "Status": "DRAFT"}
    if action == "submit_draft_po":
        return {"PurchaseOrderId": po_id, "Status": "PENDING_APPROVAL"}
    return {"error": f"unexpected action: {action}"}

mock_oracle_tool = function_tool(mock_oracle)
mock_oracle_tool.name = "oracle_connector"
mock_oracle_tool.description = oracle_connector.description

agent = Agent(
    name="procurement_agent",
    instructions=INSTRUCTION,
    tools=[mock_oracle_tool, quote_tracker, check_policy, mock_send_tool],
    output_type=EmailReply,
    model="gpt-4o",
)


def print_turn_result(reply, turn_emails_start):
    print(f"\nReply to: {reply.to}")
    print(f"Subject: {reply.subject}")
    print(f"Body:\n{reply.body[:400]}...")
    new_emails = sent_emails[turn_emails_start:]
    if new_emails:
        print(f"\n--- Emails Sent This Turn ({len(new_emails)}) ---")
        for i, email in enumerate(new_emails):
            print(f"  [{i+1}] To: {email['to']}")
            print(f"      Subject: {email['subject']}")
    print(f"\n--- Quote Tracker State ({len(_quotes)} quotes) ---")
    for vendor, quote in _quotes.items():
        print(f"  {vendor}: ${quote.get('total_price', '?'):,} total, ${quote.get('unit_price', '?')}/unit")


async def main():
    _quotes.clear()
    sent_emails.clear()
    oracle_calls.clear()

    # ── Turn 1: Sourcing ──
    print("=" * 60)
    print("TURN 1: Manager requests 500 laptops")
    print("=" * 60)

    emails_before = len(sent_emails)
    result = await Runner.run(agent, """Process this incoming email and send an appropriate reply.

From: alex.thompson@company.com
Subject: Procurement Request - 500 Business Laptops for Seattle Office
Message ID: msg-001

Email Body:
Hi Procurement Team,

We need to source 500 business laptops for our new Seattle office expansion. Here are the requirements:

- 16GB RAM, 512GB SSD minimum
- Windows 11 Pro
- Budget ceiling: $600,000
- Delivery needed by end of Q3 2026

Please reach out to our approved vendors and get competitive quotes.

Thanks,
Alex Thompson
IT Director
""")
    print_turn_result(result.final_output, emails_before)

    # ── Turn 2: Dell quote ──
    print("\n" + "=" * 60)
    print("TURN 2: Dell sends itemized quote ($1,050/unit)")
    print("=" * 60)

    emails_before = len(sent_emails)
    result = await Runner.run(agent, """Process this incoming email and send an appropriate reply.

From: sarah@dell.test
Subject: Re: RFQ: 500 Business Laptops for Seattle Office
Message ID: msg-dell-001

Email Body:
Hi Procurement Team,

Thank you for the RFQ. Here is our quote for 500 Dell Latitude 5550 laptops:

- Unit price: $1,050
- Total price: $525,000
- Specs: 16GB RAM, 512GB SSD, Intel Core i7, Windows 11 Pro
- Warranty: 3-year ProSupport
- Delivery: 4-6 weeks from PO
- Payment terms: Net 30

Please let us know if you need any additional information.

Best regards,
Sarah Johnson
Dell Technologies
""")
    print_turn_result(result.final_output, emails_before)

    # ── Turn 3: Lenovo quote with hidden handling fee ──
    print("\n" + "=" * 60)
    print("TURN 3: Lenovo sends quote with hidden handling fee")
    print("=" * 60)

    emails_before = len(sent_emails)
    result = await Runner.run(agent, """Process this incoming email and send an appropriate reply.

From: mike@lenovo.test
Subject: Re: RFQ: 500 Business Laptops for Seattle Office
Message ID: msg-lenovo-001

Email Body:
Hello,

Please find our quote for the 500 business laptops below:

- Model: Lenovo ThinkPad T14s Gen 6
- Unit price: $1,100
- Total: $550,000
- Handling and processing fee: $15,000
- Grand total: $565,000
- Specs: 16GB RAM, 512GB SSD, AMD Ryzen 7, Windows 11 Pro
- Delivery: 6-8 weeks
- Payment: 50% deposit required, balance on delivery

Best,
Mike Chen
Lenovo Sales
""")
    print_turn_result(result.final_output, emails_before)

    # ── Turn 4: HP quote ──
    print("\n" + "=" * 60)
    print("TURN 4: HP sends competitive quote")
    print("=" * 60)

    emails_before = len(sent_emails)
    result = await Runner.run(agent, """Process this incoming email and send an appropriate reply.

From: lisa@hp.test
Subject: Re: RFQ: 500 Business Laptops for Seattle Office
Message ID: msg-hp-001

Email Body:
Hi Procurement Team,

We're pleased to offer the following quote for 500 HP EliteBook 860 G11 laptops:

- Unit price: $980
- Total price: $490,000
- Specs: 16GB RAM, 512GB SSD, Intel Core i7 vPro, Windows 11 Pro
- Warranty: 3-year Next Business Day On-Site
- Delivery: 3-4 weeks from PO
- Payment terms: Net 45
- Includes free deployment imaging service

Looking forward to your decision.

Best regards,
Lisa Park
HP Inc
""")
    print_turn_result(result.final_output, emails_before)

    # ── Turn 5: Lenovo revises → should trigger finalization ──
    print("\n" + "=" * 60)
    print("TURN 5: Lenovo revises quote (should trigger finalization)")
    print("=" * 60)

    emails_before = len(sent_emails)
    oracle_calls_before = len(oracle_calls)
    result = await Runner.run(agent, """Process this incoming email and send an appropriate reply.

From: mike@lenovo.test
Subject: Re: RFQ: 500 Business Laptops for Seattle Office
Message ID: msg-lenovo-002

Email Body:
Hi,

Thank you for the feedback. We have revised our quote:

- Model: Lenovo ThinkPad T14s Gen 6
- Unit price: $1,020
- Total price: $510,000
- Handling fee: WAIVED
- Specs: 16GB RAM, 512GB SSD, AMD Ryzen 7, Windows 11 Pro
- Warranty: 3-year On-Site
- Delivery: 5-6 weeks from PO
- Payment terms: Net 30

We hope this revised offer is more competitive.

Best regards,
Mike Chen
Lenovo Sales
""")
    print_turn_result(result.final_output, emails_before)

    new_oracle_calls = oracle_calls[oracle_calls_before:]
    po_actions = [c["action"] for c in new_oracle_calls]
    print(f"\n--- Oracle Calls This Turn ---")
    for c in new_oracle_calls:
        print(f"  {c['action']} (po_id={c.get('po_id')})")

    # ── Summary ──
    all_actions = [c["action"] for c in oracle_calls]
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total emails sent: {len(sent_emails)}")
    print(f"Total oracle calls: {len(oracle_calls)}")
    print(f"Quotes stored: {list(_quotes.keys())}")
    print(f"PO created: {'create_draft_po' in all_actions}")
    print(f"PO submitted: {'submit_draft_po' in all_actions}")


asyncio.run(main())
