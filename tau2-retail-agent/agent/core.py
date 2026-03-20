import os
from pathlib import Path

AGENT_DESC_PATH = Path(
    os.environ.get("AGENT_DESC_PATH", Path(__file__).parent.parent / "agent_desc.txt")
)

SYSTEM_PROMPT_TEMPLATE = """<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>"""


def load_agent_desc() -> str:
    return AGENT_DESC_PATH.read_text().strip()


def build_system_prompt(domain_policy: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_instruction=load_agent_desc(),
        domain_policy=domain_policy,
    )
