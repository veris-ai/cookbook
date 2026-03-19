"""Knowledge Base Agent — dedicated sub-agent for RAG procedure lookups.

Vertex AI does not support mixing retrieval tools with function declaration
tools in the same generateContent request. This agent isolates the RAG tool
so it can be called via agent transfer from clear_cuid_agent.
"""

from google.adk.agents import LlmAgent

from app.config import get_settings
from app.services.tools.kb_tool import get_kb_tool

settings = get_settings()

_kb_tool = get_kb_tool()

kb_agent = LlmAgent(
    name="kb_agent",
    model=settings.adk_model,
    description="Looks up Clear CUID procedures, error types, remediation steps, "
    "and escalation rules from the knowledge base. Route here when you need to "
    "identify an error type or find the correct procedure for a CUID issue.",
    instruction="""\
You are a knowledge base lookup agent. When asked about a CUID error type,
remediation procedure, or escalation rule, use the lookup_procedure tool to
search the procedure document and return the relevant information.

Return the information clearly and concisely. Include:
- The error type code (e.g., CUID-PH-001)
- The remediation steps
- Any escalation conditions
- Required fields for the fix

Do NOT take any action — only return the procedure information.
""",
    tools=[_kb_tool],
)
