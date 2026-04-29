#!/usr/bin/env python3
"""Build tar.gz contexts and generate manifest.json for cookbook templates.

For each `<agent>/.veris/veris.yaml` in the repo:
1. Tars the agent directory (omitting any local `.env` / `.env.<name>` so a
   stray local credential never lands in a published context).
2. Unwraps the multi-target veris.yaml (cookbook standard: each file has one
   top-level target key like `mini-bcs-env:` wrapping the body — the backend's
   VerisConfig expects the unwrapped body).
3. Emits a manifest entry with curated metadata + the unwrapped veris_yaml.

Run per-environment because `image_uri` and `asset_uri` are env-specific:

    python build_contexts.py --env dev   # writes dist/manifest-dev.json
    python build_contexts.py --env prod  # writes dist/manifest-prod.json
"""

import argparse
import json
import re
import sys
import tarfile
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = REPO_ROOT / "dist"
CONTEXTS_DIR = DIST_DIR / "contexts"

SKIP_DIRS = {".github", "dist", ".git", "node_modules", "__pycache__"}

SECRET_PATTERN = re.compile(r"\$\{(\w+)\}")
PLACEHOLDER_PATTERN = re.compile(r"<your-[^>]+>")

# Top-level keys in veris.yaml that mark the unwrapped (single-target) shape.
# If any of these appear at the top level, treat the file as unwrapped.
BODY_KEYS = {"services", "actor", "persona", "agent"}
META_KEYS = {"version", "simulation_id"}

# Per-environment GCS + Artifact Registry conventions. The script renders
# manifest entries with paths matching the environment we're publishing to.
ENV_CONFIG: dict[str, dict[str, str]] = {
    "dev": {
        "registry": "us-central1-docker.pkg.dev/veris-ai-dev/veris-sandbox",
        "bucket": "veris-sandbox-blob-storage-dev",
    },
    "prod": {
        "registry": "us-central1-docker.pkg.dev/veris-ai-prod/veris-sandbox",
        "bucket": "veris-sandbox-blob-storage-prod",
    },
}

GITHUB_REPO_URL = "https://github.com/veris-ai/cookbook"

# Curated per-template metadata. Add a new template here when publishing one;
# build_entry() reads via direct subscript, so a missing entry will fail loudly
# rather than ship a manifest row with null fields.
REQUIRED_METADATA_KEYS = {
    "name",
    "description",
    "framework",
    "llm_provider",
    "actors",
    "architecture",
}

TEMPLATES: dict[str, dict[str, str]] = {
    "bca-agent": {
        "name": "Banker Connections Agent",
        "description": (
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
        "framework": "google-adk",
        "llm_provider": "gemini",
        "actors": "single",
        "architecture": "multi-agent",
    },
    "card-replacement-agent": {
        "name": "Card Replacement Agent",
        "description": (
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
        "framework": "openai-agents-sdk",
        "llm_provider": "openai",
        "actors": "single",
        "architecture": "multi-agent",
    },
    "medical-triage-agent": {
        "name": "Medical Triage Agent",
        "description": (
            "A conversational agent that triages patients to the right medical specialist. "
            "Connects to an Epic FHIR R4 API using the fhirclient SDK to look up patient "
            "records, gathers symptoms through multi-turn conversation, recommends a "
            "specialist referral with urgency level (Routine / Urgent / Emergent), and "
            "books the appointment — all through a single WebSocket session. Built with "
            "PydanticAI on Amazon Bedrock AgentCore, defaulting to Amazon Nova Pro."
        ),
        "framework": "pydantic-ai",
        "llm_provider": "bedrock",
        "actors": "single",
        "architecture": "single-agent",
    },
    "mini-bcs": {
        "name": "Bank Customer Service",
        "description": (
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
        "framework": "openai-agents-sdk",
        "llm_provider": "openai",
        "actors": "single",
        "architecture": "single-agent",
    },
    "pm-analyst": {
        "name": "PM Analyst",
        "description": (
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
        "framework": "google-adk",
        "llm_provider": "gemini",
        "actors": "single",
        "architecture": "single-agent",
    },
    "procurement-agent": {
        "name": "Procurement Agent",
        "description": (
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
        "framework": "openai-agents-sdk",
        "llm_provider": "openai",
        "actors": "multi",
        "architecture": "single-agent",
    },
    "shopping-agent": {
        "name": "Shopping Agent",
        "description": (
            "A multi-agent online store assistant that handles product browsing, purchases, "
            "order history, and refunds. Uses a LangGraph supervisor pattern with two "
            "specialist agents: a catalog agent (OpenAI/Stripe MCP) for product search, "
            "pricing, payment links, and refunds, and an account agent (Gemini/PostgreSQL) "
            "for customer profiles, order history, and profile updates. A typical "
            "interaction: a customer asks to buy a hoodie — the supervisor delegates to the "
            "account agent to look up the customer and loyalty points, then to the catalog "
            "agent to find the product and create a payment link, then back to the account "
            "agent to record the order."
        ),
        "framework": "langchain",
        "llm_provider": "openai",
        "actors": "single",
        "architecture": "multi-agent",
    },
}


def find_templates() -> list[Path]:
    templates = []
    for entry in sorted(REPO_ROOT.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        if (entry / ".veris" / "veris.yaml").exists():
            templates.append(entry)
    return templates


def unwrap_veris_yaml(raw: dict, template_id: str) -> dict:
    """Hoist the single target's body to the top level.

    Cookbook veris.yaml uses the multi-target shape: a top-level key like
    `mini-bcs-env:` wraps the body. The backend's VerisConfig only validates
    the unwrapped body, so the manifest's `veris_yaml` field must be flat.

    Fails loudly if the file has multiple targets — the manifest format only
    supports one target per template, and silently picking one would mask bugs.
    """
    if any(k in raw for k in BODY_KEYS):
        # Already flat. Cookbook main shouldn't use this shape today, but keep
        # the path for callers that hand-write a flat veris.yaml.
        return raw

    targets = {k: v for k, v in raw.items() if k not in META_KEYS and isinstance(v, dict)}
    if len(targets) != 1:
        raise SystemExit(
            f"{template_id}: expected exactly 1 target in veris.yaml, "
            f"got {len(targets)}: {sorted(targets)}"
        )

    body = next(iter(targets.values()))
    out: dict = {}
    if "version" in raw:
        out["version"] = raw["version"]
    out.update(body)
    return out


def extract_required_vars(veris_yaml: dict, template_dir: Path) -> list[str]:
    """Collect env vars the user must supply (referenced via ${VAR} or <your-...>)."""
    required: set[str] = set()

    for key, value in veris_yaml.get("agent", {}).get("environment", {}).items():
        s = str(value)
        for var_name in SECRET_PATTERN.findall(s):
            required.add(var_name)
        if PLACEHOLDER_PATTERN.search(s) and not SECRET_PATTERN.search(s):
            required.add(key)

    env_example = template_dir / ".env.example"
    if env_example.exists():
        for line in env_example.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value in ("REPLACE_ME", "") or value.startswith("sk-") or "your-key" in value.lower():
                required.add(key)

    return sorted(required)


def extract_channel(veris_yaml: dict, template_id: str) -> str:
    """Return the primary channel type. Fails loudly if no actor.channels.

    The legacy `persona.modality` fallback was removed when sandbox dropped
    its back-compat shims — keeping it here would re-create the silent-drop
    bug that motivated this script.
    """
    channels = veris_yaml.get("actor", {}).get("channels")
    if not channels or not isinstance(channels, list):
        raise SystemExit(
            f"{template_id}: no actor.channels found in veris.yaml — "
            f"every template must declare at least one channel under actor.channels"
        )
    return channels[0].get("type", "http")


def extract_services(veris_yaml: dict) -> list[str]:
    return [s.get("name", "") for s in veris_yaml.get("services", []) if isinstance(s, dict)]


def _tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Drop dotenv files so a stray local .env never ships in a published context.

    Keeps `.env.example` (it's intentional template documentation) and any
    other file unchanged. Anything matching `.env` or `.env.<suffix>` is
    excluded — covers `.env`, `.env.local`, `.env.production`, etc.
    """
    name = Path(tarinfo.name).name
    if name == ".env.example":
        return tarinfo
    if name == ".env" or name.startswith(".env."):
        return None
    return tarinfo


def build_tar(template_dir: Path) -> Path:
    output_path = CONTEXTS_DIR / f"{template_dir.name}.tar.gz"
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(template_dir, arcname=".", filter=_tar_filter)
    return output_path


def build_entry(template_dir: Path, env_cfg: dict[str, str]) -> dict[str, Any]:
    template_id = template_dir.name
    if template_id not in TEMPLATES:
        raise SystemExit(
            f"{template_id}: no metadata entry in TEMPLATES — add one in "
            f"{Path(__file__).relative_to(REPO_ROOT)} before publishing"
        )
    meta = TEMPLATES[template_id]
    missing = REQUIRED_METADATA_KEYS - meta.keys()
    if missing:
        raise SystemExit(f"{template_id}: TEMPLATES entry missing keys: {sorted(missing)}")

    raw = yaml.safe_load((template_dir / ".veris" / "veris.yaml").read_text())
    veris_yaml = unwrap_veris_yaml(raw, template_id)

    return {
        "id": template_id,
        "name": meta["name"],
        "description": meta["description"],
        "channel": extract_channel(veris_yaml, template_id),
        "services": extract_services(veris_yaml),
        "framework": meta["framework"],
        "llm_provider": meta["llm_provider"],
        "actors": meta["actors"],
        "architecture": meta["architecture"],
        "required_vars": extract_required_vars(veris_yaml, template_dir),
        "image_uri": f"{env_cfg['registry']}/cookbook-{template_id}:latest",
        "asset_uri": f"gs://{env_cfg['bucket']}/templates/assets/{template_id}",
        "github_url": f"{GITHUB_REPO_URL}/tree/main/{template_id}",
        "veris_yaml": veris_yaml,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=sorted(ENV_CONFIG))
    args = parser.parse_args()

    env_cfg = ENV_CONFIG[args.env]
    DIST_DIR.mkdir(exist_ok=True)
    CONTEXTS_DIR.mkdir(exist_ok=True)

    templates = find_templates()
    if not templates:
        print("No templates found", file=sys.stderr)
        sys.exit(1)

    manifest: dict[str, list[dict[str, Any]]] = {"templates": []}
    for template_dir in templates:
        print(f"Processing {template_dir.name}...")
        entry = build_entry(template_dir, env_cfg)
        build_tar(template_dir)
        manifest["templates"].append(entry)
        print(
            f"  channel={entry['channel']}, services={entry['services']}, "
            f"framework={entry['framework']}, required_vars={entry['required_vars']}"
        )

    manifest_path = DIST_DIR / f"manifest-{args.env}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    print(f"\nWrote {len(manifest['templates'])} templates → {manifest_path}")


if __name__ == "__main__":
    main()
