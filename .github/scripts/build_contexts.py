#!/usr/bin/env python3
"""Build tar.gz contexts and generate manifest.json for cookbook templates.

Scans each directory in the repo root for .veris/veris.yaml. For each template found:
1. Creates a tar.gz of the build context (the template directory)
2. Parses veris.yaml to extract metadata (channel, services, required vars)
3. Generates a manifest.json with all template metadata
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = REPO_ROOT / "dist"
CONTEXTS_DIR = DIST_DIR / "contexts"

# Artifact Registry for pre-built cookbook images
ARTIFACT_REGISTRY = os.environ.get("ARTIFACT_REGISTRY", "")

# Directories to skip
SKIP_DIRS = {".github", "dist", ".git", "node_modules", "__pycache__"}

# Patterns that indicate a user-provided value
SECRET_PATTERN = re.compile(r"\$\{(\w+)\}")
PLACEHOLDER_PATTERN = re.compile(r"<your-[^>]+>")

# ── Template metadata ──

DISPLAY_NAMES: dict[str, str] = {
    "bca-agent": "Banker Connections Agent",
    "card-replacement-agent": "Card Replacement Agent",
    "mini-bcs": "Bank Customer Service",
    "pm-analyst": "PM Analyst",
    "procurement-agent": "Procurement Agent",
}

DESCRIPTIONS: dict[str, str] = {
    "bca-agent": (
        "Helps retail bankers resolve customer record update errors on the spot, "
        "eliminating 12-15 minute calls to back-office specialists. When a banker "
        "encounters a phone number or ID document update failure in the Hogan core "
        "banking system, this agent walks them through the error, identifies the root "
        "cause from five known Clear CUID scenarios, retrieves the remediation procedure "
        "from a Vertex AI RAG knowledge base, pulls the customer profile from Hogan, "
        "and executes the fix with banker confirmation. For example, a banker sees "
        "'CUID-PH-001' after trying to update a customer's phone — the agent looks up "
        "the procedure, fetches the customer record, proposes clearing the conflicting "
        "field, and patches Hogan once the banker approves."
    ),
    "card-replacement-agent": (
        "A multi-agent banking assistant that handles the full card replacement lifecycle "
        "— freezing compromised cards, ordering replacements, tracking delivery, and "
        "activating new cards. Built with the OpenAI Agents SDK, it uses a triage agent "
        "to route requests to specialized sub-agents: one for replacement (collects reason, "
        "identifies the card by last four digits, freezes if stolen/lost, sets up a "
        "14-business-day replacement), one for status updates and activation, and one for "
        "out-of-scope redirects. All customer and card data lives in PostgreSQL. A typical "
        "interaction: a customer reports a stolen card, the agent freezes it immediately, "
        "initiates a replacement to the address on file, and confirms the expected delivery "
        "window."
    ),
    "mini-bcs": (
        "A streamlined credit card customer support agent that handles card replacement "
        "and status inquiries end-to-end using a single unified agent (no sub-agent routing). "
        "Supports multiple LLM providers including OpenAI, Azure OpenAI, DeepSeek, Grok, "
        "and others — configurable via a single environment variable. The agent manages the "
        "full workflow against a PostgreSQL customer database: collecting the reason for "
        "replacement, identifying the right card, freezing stolen or lost cards, scheduling "
        "replacements, confirming delivery details, and activating new cards on arrival. "
        "For example, a customer calls to check on a replacement they requested last week "
        "— the agent looks up the card status, reports it was mailed two days ago, and "
        "offers to activate it once it arrives."
    ),
    "pm-analyst": (
        "Turns meeting recordings and documents into structured project management artifacts "
        "in Azure DevOps. The agent connects to Microsoft Graph to pull Teams meeting "
        "transcripts or OneDrive files, produces a summary with key decisions, action items, "
        "and open questions, then generates Epics, Features, and User Stories with proper "
        "hierarchy and pushes them to ADO. Communicates over WebSocket for real-time "
        "back-and-forth. A typical session: PM selects last Tuesday's sprint planning meeting, "
        "the agent parses the transcript, surfaces three decisions and five action items, "
        "asks one clarifying question about scope, then creates an Epic with two Features "
        "and four User Stories in the team's ADO project."
    ),
    "procurement-agent": (
        "An autonomous IT procurement agent that manages the full sourcing-to-PO lifecycle "
        "via email, integrated with Oracle Fusion Cloud ERP. The agent operates in three "
        "phases: first it reads a purchase requisition from Oracle, fetches approved suppliers "
        "and their contacts, and sends personalized RFQ emails to each vendor. As quotes come "
        "back, it extracts pricing, compares bids, negotiates counter-offers (without revealing "
        "budget or competitor details), and flags hidden fees or missing itemization. Once enough "
        "quotes are collected, it selects the best-value vendor, validates against procurement "
        "policy (budget caps, minimum quote count, approved supplier list), creates a draft PO "
        "in Oracle, submits it, and notifies the winning vendor. For example, a requisition for "
        "50 laptops triggers RFQs to three approved suppliers — the agent negotiates one vendor "
        "down 12%, rejects another for exceeding budget, and creates the PO with the winning bid."
    ),
}

FRAMEWORKS: dict[str, str] = {
    "bca-agent": "google-adk",
    "card-replacement-agent": "openai-agents-sdk",
    "mini-bcs": "openai-agents-sdk",
    "pm-analyst": "google-adk",
    "procurement-agent": "openai-agents-sdk",
}

LLM_PROVIDERS: dict[str, str] = {
    "bca-agent": "gemini",
    "card-replacement-agent": "openai",
    "mini-bcs": "openai",
    "pm-analyst": "gemini",
    "procurement-agent": "openai",
}

ACTORS: dict[str, str] = {
    "bca-agent": "single",
    "card-replacement-agent": "single",
    "mini-bcs": "single",
    "pm-analyst": "single",
    "procurement-agent": "multi",
}

ARCHITECTURES: dict[str, str] = {
    "bca-agent": "multi-agent",
    "card-replacement-agent": "multi-agent",
    "mini-bcs": "single-agent",
    "pm-analyst": "single-agent",
    "procurement-agent": "single-agent",
}


def find_templates() -> list[Path]:
    """Find directories containing .veris/veris.yaml."""
    templates = []
    for entry in sorted(REPO_ROOT.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        veris_yaml = entry / ".veris" / "veris.yaml"
        if veris_yaml.exists():
            templates.append(entry)
    return templates


def parse_veris_yaml(template_dir: Path) -> dict:
    """Parse veris.yaml and return the raw dict."""
    veris_yaml_path = template_dir / ".veris" / "veris.yaml"
    with open(veris_yaml_path) as f:
        return yaml.safe_load(f)


def extract_required_vars(veris_yaml: dict, template_dir: Path) -> list[str]:
    """Extract variable names that require user input.

    Sources (in priority order):
    1. veris.yaml agent.environment: ${VAR_NAME} and <your-...> patterns
    2. .env.example: REPLACE_ME values and known API key patterns
    """
    required = set()

    # Source 1: veris.yaml
    agent_env = veris_yaml.get("agent", {}).get("environment", {})
    for key, value in agent_env.items():
        value_str = str(value)
        if SECRET_PATTERN.search(value_str):
            match = SECRET_PATTERN.search(value_str)
            required.add(match.group(1))
        elif PLACEHOLDER_PATTERN.search(value_str):
            required.add(key)

    # Source 2: .env.example
    env_example = template_dir / ".env.example"
    if env_example.exists():
        for line in env_example.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value in ("REPLACE_ME", ""):
                required.add(key)
            elif value.startswith("sk-") or "your-key" in value.lower():
                required.add(key)

    return sorted(required)


def extract_channel(veris_yaml: dict) -> str:
    """Extract the primary channel type from veris.yaml."""
    # Try actor.channels first (newer format)
    channels = veris_yaml.get("actor", {}).get("channels", [])
    if channels and isinstance(channels, list):
        return channels[0].get("type", "http")

    # Try persona.modality (older format)
    modality = veris_yaml.get("persona", {}).get("modality", {})
    if isinstance(modality, dict):
        return modality.get("type", "http")

    return "http"


def extract_services(veris_yaml: dict) -> list[str]:
    """Extract service names from veris.yaml."""
    services = veris_yaml.get("services", [])
    return [s.get("name", "") for s in services if isinstance(s, dict)]


def build_tar(template_dir: Path) -> Path:
    """Create tar.gz of the template directory."""
    template_id = template_dir.name
    output_path = CONTEXTS_DIR / f"{template_id}.tar.gz"
    subprocess.run(
        ["tar", "-czf", str(output_path), "-C", str(template_dir), "."],
        check=True,
    )
    return output_path


def main():
    DIST_DIR.mkdir(exist_ok=True)
    CONTEXTS_DIR.mkdir(exist_ok=True)

    templates = find_templates()
    if not templates:
        print("No templates found", file=sys.stderr)
        sys.exit(1)

    manifest = {"templates": []}

    for template_dir in templates:
        template_id = template_dir.name
        print(f"Processing {template_id}...")

        veris_yaml = parse_veris_yaml(template_dir)
        tar_path = build_tar(template_dir)
        tar_size = tar_path.stat().st_size

        entry = {
            "id": template_id,
            "name": DISPLAY_NAMES.get(template_id, template_id),
            "description": DESCRIPTIONS.get(template_id, ""),
            "channel": extract_channel(veris_yaml),
            "services": extract_services(veris_yaml),
            "framework": FRAMEWORKS.get(template_id),
            "llm_provider": LLM_PROVIDERS.get(template_id),
            "actors": ACTORS.get(template_id),
            "architecture": ARCHITECTURES.get(template_id),
            "required_vars": extract_required_vars(veris_yaml, template_dir),
            "veris_yaml": veris_yaml,
        }

        manifest["templates"].append(entry)
        print(f"  channel={entry['channel']}, services={entry['services']}, "
              f"framework={entry['framework']}, llm={entry['llm_provider']}, "
              f"required_vars={entry['required_vars']}, size={tar_size} bytes")

    manifest_path = DIST_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(f"\nGenerated manifest with {len(manifest['templates'])} templates")
    print(f"Output: {DIST_DIR}")


if __name__ == "__main__":
    main()
