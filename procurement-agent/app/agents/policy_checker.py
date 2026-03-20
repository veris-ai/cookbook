from typing import Any

from agents import Agent, Runner, RunContextWrapper, function_tool
from pydantic import BaseModel

from app.agents.context import ProcurementContext


class PolicyDecision(BaseModel):
    decision: str
    reason: str
    violations: list[str]


POLICY_INSTRUCTIONS = """You are a procurement policy checker. Analyze the proposed action and return a decision.

IMPORTANT: Compare numbers carefully. Only reject if the amount is strictly GREATER than the budget ceiling.

## Policy Rules
1. Total cost must not exceed budget ceiling: REJECT only if amount > budget_ceiling
2. Deposits must not exceed 20% of total amount
3. Unit price must not exceed $1,200
4. Minimum 3 competitive quotes required before final recommendation: REJECT if quotes_collected < 3
5. Vendor must be on the Approved Supplier List: REJECT if "NO - VIOLATION" is indicated
6. Single line items exceeding $100,000 require escalation

## Semantic Checks (only if email_draft is provided)
- Flag commitment language ("we accept", "deal", "agreed") — agent should not commit without approval
- Flag hidden fees or unclear pricing
- Flag missing warranty/return terms
- Flag lump-sum pricing without itemization
- Flag any leaking of budget or competing quote details to vendor
- Flag pressure tactics or artificial urgency from vendor

## Decision Rules
- REJECT if any hard policy rule is violated (rules 1-5)
- ESCALATE if rule 6 triggered, or semantic issues found in email draft
- APPROVE if all rules pass and no semantic issues. Set violations to empty list.
"""

_policy_agent = Agent(
    name="policy_checker",
    instructions=POLICY_INSTRUCTIONS,
    output_type=PolicyDecision,
    model="gpt-4o",
)


@function_tool
async def check_policy(
    ctx: RunContextWrapper[ProcurementContext],
    proposed_action: str,
    amount: float,
    terms_summary: str,
    vendor_name: str,
    quotes_collected: int = 0,
    budget_ceiling: float = 0,
    email_draft: str | None = None,
) -> dict[str, Any]:
    """Check proposed action against procurement policies before committing.

    Call this before: accepting a quote, agreeing to terms, paying a deposit, or sending a commitment email.
    Returns approve/reject/escalate with reason and any violations found.
    """
    effective_budget = budget_ceiling if budget_ceiling > 0 else ctx.context.budget_ceiling
    over_budget = amount > effective_budget if effective_budget > 0 else False
    enough_quotes = quotes_collected >= 3

    asl = ctx.context.approved_suppliers
    if asl:
        supplier_names = [(s.get("SupplierName") or s.get("Supplier") or "").lower() for s in asl]
        on_asl = vendor_name.lower() in supplier_names
    else:
        on_asl = True  # ASL not loaded yet, cannot verify

    input_msg = f"""Proposed action: {proposed_action}
Amount: ${amount:,.2f}
Vendor: {vendor_name}
Terms: {terms_summary}
Quotes collected: {quotes_collected} ({"meets" if enough_quotes else "DOES NOT meet"} minimum 3 requirement)
Budget ceiling: ${effective_budget:,.2f} ({"OVER BUDGET" if over_budget else "within budget"})
Vendor on Approved Supplier List: {"YES" if on_asl else "NO - VIOLATION"}"""

    if email_draft:
        input_msg += f"\n\nEmail draft to review:\n{email_draft}"

    result = await Runner.run(_policy_agent, input_msg)
    output: PolicyDecision = result.final_output
    return output.model_dump()
