"""Quick test: verify policy checker returns structured approve/reject/escalate decisions."""

import asyncio
import json

from dotenv import load_dotenv
load_dotenv()

from agents import Runner, set_default_openai_key
from app.agents.policy_checker import check_policy, _policy_agent, PolicyDecision
from app.config import get_settings

set_default_openai_key(get_settings().openai_api_key)


async def main():
    print("=" * 60)
    print("TEST 1: Should APPROVE — valid quote acceptance")
    print("=" * 60)
    result = await Runner.run(_policy_agent, """Proposed action: accept_quote
Amount: $525,000.00
Vendor: Dell
Terms: Net 30, 3-year warranty, 4-6 week delivery
Quotes collected so far: 3
Budget ceiling: $600,000.00""")
    output: PolicyDecision = result.final_output
    print(json.dumps(output.model_dump(), indent=2))

    print("\n" + "=" * 60)
    print("TEST 2: Should REJECT — over budget")
    print("=" * 60)
    result = await Runner.run(_policy_agent, """Proposed action: accept_quote
Amount: $700,000.00
Vendor: Lenovo
Terms: Net 45
Quotes collected so far: 3
Budget ceiling: $600,000.00""")
    output = result.final_output
    print(json.dumps(output.model_dump(), indent=2))

    print("\n" + "=" * 60)
    print("TEST 3: Should REJECT — only 1 quote collected")
    print("=" * 60)
    result = await Runner.run(_policy_agent, """Proposed action: accept_quote
Amount: $525,000.00
Vendor: Dell
Terms: Net 30
Quotes collected so far: 1
Budget ceiling: $600,000.00""")
    output = result.final_output
    print(json.dumps(output.model_dump(), indent=2))

    print("\n" + "=" * 60)
    print("TEST 4: Should ESCALATE — commitment language in email draft")
    print("=" * 60)
    result = await Runner.run(_policy_agent, """Proposed action: agree_terms
Amount: $525,000.00
Vendor: Dell
Terms: Net 30, 3-year warranty
Quotes collected so far: 3
Budget ceiling: $600,000.00

Email draft to review:
Hi Dell,

We accept your quote and would like to proceed immediately. Please consider this our commitment to the purchase. We'll send the PO shortly.

Best regards""")
    output = result.final_output
    print(json.dumps(output.model_dump(), indent=2))


asyncio.run(main())
