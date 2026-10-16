"""One agent in place of the triage + three specialists: the union of their tools, their
routines merged into one instruction (agent_desc.yaml, single_agent). Selected by
CARD_AGENT_TOPOLOGY=single in app.main; the model pin (CARD_AGENT_MODEL) is shared."""
from agents import Agent

from .agent_tools import (
    change_card_status,
    display_card_info_by_last4,
    display_user_info,
    request_card_replacement,
    update_card_replacement_status,
)
from .subagents import MODEL, agent_desc

single_agent = Agent(
    name="Card Services Agent",
    model=MODEL,
    instructions=agent_desc["Agent"]["single_agent"]["instructions"],
    tools=[
        display_user_info,
        display_card_info_by_last4,
        change_card_status,
        request_card_replacement,
        update_card_replacement_status,
    ],
)
