"""HolmesGPT investigation pipeline wrapped for a single PagerDuty incident.

PagerDuty is consumed as a *Source* — our Python code fetches the incident and
writes the analysis back as a note. The LLM never calls PagerDuty.

Datadog is consumed as a *Toolset* — the LLM decides when to call
`fetch_datadog_logs` and `query_datadog_metrics` during the investigation. The
Holmes config that enables those (and disables every other built-in toolset)
lives at `.holmes/config.yaml` and is loaded via `HOLMES_CONFIGPATH_DIR`.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

from holmes.config import Config
from holmes.core.config import config_path_dir
from holmes.core.prompt import build_system_prompt, generate_user_prompt
from holmes.core.tool_calling_llm import LLMResult, ToolCallingLLM
from holmes.core.tools import ToolsetTag
from holmes.plugins.interfaces import Issue
from holmes.plugins.sources.pagerduty import PagerDutySource

logger = logging.getLogger(__name__)

_INCIDENT_ID_RE = re.compile(r"\bP[A-Z0-9]{5,}\b")


def parse_incident_id(message: str) -> Optional[str]:
    """Extract a PagerDuty incident ID (e.g. PT4KHLK) from free-form text."""
    match = _INCIDENT_ID_RE.search(message or "")
    return match.group(0) if match else None


def build_config() -> Config:
    """Build a HolmesGPT Config, merging the Datadog toolset config from .holmes/config.yaml."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set OPENAI_API_KEY or ANTHROPIC_API_KEY for HolmesGPT's LLM client."
        )

    config_file = Path(config_path_dir) / "config.yaml"
    if not config_file.exists():
        logger.warning(
            "Holmes config not found at %s — Datadog toolset will not load.",
            config_file,
        )

    return Config.load_from_file(
        config_file,
        api_key=api_key,
        model=os.environ.get("MODEL", "openai/gpt-5.4-mini"),
        pagerduty_api_key=os.environ.get("PAGERDUTY_API_TOKEN"),
        pagerduty_user_email=os.environ.get("PAGERDUTY_USER_EMAIL", "sre-bot@holmesgpt.local"),
    )


def build_source(config: Config, incident_key: Optional[str] = None) -> PagerDutySource:
    return PagerDutySource(
        api_key=config.pagerduty_api_key.get_secret_value(),  # type: ignore[union-attr]
        user_email=config.pagerduty_user_email,  # type: ignore[arg-type]
        incident_key=incident_key,
    )


def pick_incident(source: PagerDutySource, incident_id: Optional[str]) -> Optional[Issue]:
    """Resolve a single Issue: by ID if given, else the most recent triggered one."""
    if incident_id:
        return source.fetch_issue(incident_id)

    issues = source.fetch_issues()
    if not issues:
        return None
    return issues[0]


def investigate(ai: ToolCallingLLM, issue: Issue, config: Config) -> LLMResult:
    """Run HolmesGPT's standard investigation prompt against a PagerDuty issue.

    Mirrors holmes.main._investigate_issue without the CLI rendering.
    """
    additions = (
        f"Provide a terse analysis of the following {issue.source_type} "
        "alert/issue and why it is firing."
    )
    system_prompt = build_system_prompt(
        toolsets=ai.tool_executor.toolsets,
        skills=None,
        system_prompt_additions=additions,
        cluster_name=config.cluster_name,
        ask_user_enabled=False,
        prompt_component_overrides={},
    )
    user_prompt = generate_user_prompt(
        f"\n #This is context from the issue:\n{issue.raw}",
        context={},
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return ai.call(messages)


def make_toolcalling_llm(config: Config) -> ToolCallingLLM:
    # Datadog is the only toolset surface: the CORE tag filter lets the
    # datadog/* toolsets through, and enable_all_toolsets_possible=False means
    # only the ones explicitly enabled in .holmes/config.yaml actually load.
    # No kubectl, Prometheus, Grafana, bash, etc.
    return config.create_toolcalling_llm(
        toolset_tag_filter=[ToolsetTag.CORE],
        enable_all_toolsets_possible=False,
    )
