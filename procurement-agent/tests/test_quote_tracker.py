"""Quick test: send a fake vendor quote email through the agent and verify quote_tracker is called."""

import asyncio
import json

from dotenv import load_dotenv
load_dotenv()

from agents import Agent, Runner, set_default_openai_key

from app.agents.tools import quote_tracker, _quotes
from app.config import get_settings

set_default_openai_key(get_settings().openai_api_key)

INSTRUCTION = """You are a procurement agent that processes vendor quote emails.

When you receive a vendor quote email:
1. Extract pricing, timeline, scope, terms, warranty, and delivery details
2. Call quote_tracker with action="store" to save the quote
3. Reply confirming receipt of the quote

When asked to compare quotes:
1. Call quote_tracker with action="compare"
2. Summarize the comparison in your reply

Reply format: set "to" to sender, "subject" to "Re: <original subject>", keep tone professional.
"""

from pydantic import BaseModel

class EmailReply(BaseModel):
    to: str
    subject: str
    body: str
    in_reply_to: str | None = None


agent = Agent(
    name="procurement_agent",
    instructions=INSTRUCTION,
    tools=[quote_tracker],
    output_type=EmailReply,
    model="gpt-4o",
)


async def main():
    _quotes.clear()

    print("=" * 60)
    print("STEP 1: Send Dell quote email")
    print("=" * 60)

    dell_email = """Process this incoming email and send an appropriate reply.

From: sales@dell.com
Subject: Quote for 500 Latitude 5550 Laptops
Message ID: msg-001

Email Body:
Hi,

Thank you for your inquiry. Here is our quote for the 500 Latitude 5550 laptops:

- Unit Price: $1,050
- Total Price: $525,000
- Scope: 500x Dell Latitude 5550, 16GB RAM, 512GB SSD, Windows 11 Pro
- Timeline: 4-6 weeks from PO receipt
- Delivery Date: March 15, 2026
- Terms: Net 30
- Warranty: 3-year ProSupport on-site

Please let us know if you'd like to proceed.

Best regards,
Dell Sales Team
"""

    result = await Runner.run(agent, dell_email)
    reply = result.final_output
    print(f"Reply to: {reply.to}")
    print(f"Subject: {reply.subject}")
    print(f"Body: {reply.body[:200]}...")
    print(f"\nStored quotes: {json.dumps(list(_quotes.keys()))}")
    print(f"Dell quote: {json.dumps(_quotes.get('Dell', _quotes.get('dell', {})), indent=2)}")

    print("\n" + "=" * 60)
    print("STEP 2: Send Lenovo quote email")
    print("=" * 60)

    lenovo_email = """Process this incoming email and send an appropriate reply.

From: enterprise@lenovo.com
Subject: RE: RFQ - 500 ThinkPad T14s Laptops
Message ID: msg-002

Email Body:
Dear Procurement Team,

We are pleased to submit our quote:

- Unit Price: $1,100
- Total Price: $550,000
- Scope: 500x Lenovo ThinkPad T14s Gen 5, 16GB RAM, 512GB SSD, Windows 11 Pro
- Timeline: 3-4 weeks
- Terms: Net 45
- Warranty: 3-year on-site with accidental damage protection

Delivery date to be confirmed upon PO.

Regards,
Lenovo Enterprise Sales
"""

    result = await Runner.run(agent, lenovo_email)
    reply = result.final_output
    print(f"Reply to: {reply.to}")
    print(f"Subject: {reply.subject}")
    print(f"\nStored quotes: {json.dumps(list(_quotes.keys()))}")

    print("\n" + "=" * 60)
    print("STEP 3: Ask agent to compare quotes")
    print("=" * 60)

    compare_email = """Process this incoming email and send an appropriate reply.

From: manager@company.com
Subject: Vendor Quote Comparison
Message ID: msg-003

Email Body:
Can you compare the vendor quotes we've received so far and summarize which vendor offers the best value?
"""

    result = await Runner.run(agent, compare_email)
    reply = result.final_output
    print(f"Reply to: {reply.to}")
    print(f"Subject: {reply.subject}")
    print(f"Body:\n{reply.body}")

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    print(json.dumps(_quotes, indent=2))


asyncio.run(main())
