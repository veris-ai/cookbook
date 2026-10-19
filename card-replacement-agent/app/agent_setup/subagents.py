from agents import Agent, RunContextWrapper, handoff
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from .agent_tools import display_user_info, change_card_status, request_card_replacement, update_card_replacement_status, display_card_info_by_last4

import os
import yaml

with open("agent_desc.yaml", "r") as f:
    agent_desc = yaml.safe_load(f)

# CARD_AGENT_MODEL pins every agent to one model (e.g. gpt-5.6-sol); unset keeps the
# openai-agents default. The model settings stay the SDK's plain defaults either way.
MODEL = os.environ.get("CARD_AGENT_MODEL") or None


triage_agent = Agent(
    name="Triage Agent",
    model=MODEL,
    instructions=f"{RECOMMENDED_PROMPT_PREFIX}\nYou can only handoff to one agent at a time. \n{agent_desc['Agent']['triage_agent']['instructions']}",
)

card_replacement_agent = Agent(
    name="Card Replacement Agent",
    model=MODEL,
    instructions=agent_desc["Agent"]["card_replacement_agent"]["instructions"],
    tools=[display_user_info, display_card_info_by_last4, change_card_status, request_card_replacement],
    handoffs=[handoff(triage_agent)]
)

card_replacement_status_update_agent = Agent(
    name="Card Replacement Status Update Agent",
    model=MODEL,
    instructions=agent_desc["Agent"]["card_replacement_status_update_agent"]["instructions"],
    tools=[display_card_info_by_last4, display_user_info, change_card_status, update_card_replacement_status],
    handoffs=[handoff(triage_agent)]
)

oos_agent = Agent(
    name="Out of Scope Agent",
    model=MODEL,
    instructions=agent_desc["Agent"]["oos_agent"]["instructions"],
    handoffs=[handoff(triage_agent)]
)

triage_agent.handoffs = [handoff(card_replacement_agent), handoff(card_replacement_status_update_agent), handoff(oos_agent)]
