#!/usr/bin/env python3
"""Build tar.gz contexts and generate manifest.json for cookbook templates.

For each `<agent>/.veris/veris.yaml` in the repo:
1. Tars the agent directory.
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
import subprocess
import sys
from pathlib import Path

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

# ── Curated per-template metadata. Add a new template here when publishing one. ──

DISPLAY_NAMES: dict[str, str] = {
    "bca-agent": "Banker Connections Agent",
    "card-replacement-agent": "Card Replacement Agent",
    "medical-triage-agent": "Medical Triage Agent",
    "mini-bcs": "Bank Customer Service",
    "pm-analyst": "PM Analyst",
    "procurement-agent": "Procurement Agent",
    "shopping-agent": "Shopping Agent",
}

DESCRIPTIONS: dict[str, str] = {
    "bca-agent": (
        "Helps retail bankers resolve customer record update errors on the spot, "
        "eliminating 12-15 minute calls to back-office specialists. When a banker "
        "encounters a phone number or ID document update failure in the Hogan core "
        "banking system, this agent walks them through the error, identifies the root "
        "cause from five known Clear CUID scenarios, retrieves the remediation procedure "
        "from a Vertex AI RAG knowledge base, pulls the customer profile from Hogan, "
        "and executes the fix with banker confirmation."
    ),
    "card-replacement-agent": (
        "A multi-agent banking assistant that handles the full card replacement lifecycle "
        "— freezing compromised cards, ordering replacements, tracking delivery, and "
        "activating new cards. Built with the OpenAI Agents SDK, it uses a triage agent "
        "to route requests to specialized sub-agents."
    ),
    "medical-triage-agent": (
        "A healthcare triage assistant that gathers symptoms over a WebSocket conversation, "
        "queries an Epic FHIR mock for patient context, and routes the case to the "
        "appropriate level of care. Useful for evaluating clinical safety guardrails, "
        "history-taking quality, and adherence to triage protocols."
    ),
    "mini-bcs": (
        "A streamlined credit card customer support agent that handles card replacement "
        "and status inquiries end-to-end using a single unified agent. Supports multiple "
        "LLM providers via a single environment variable. Manages the full workflow "
        "against a PostgreSQL customer database: collecting reasons for replacement, "
        "freezing stolen or lost cards, scheduling replacements, and activating new cards."
    ),
    "pm-analyst": (
        "Turns meeting recordings and documents into structured project management artifacts "
        "in Azure DevOps. Connects to Microsoft Graph to pull Teams meeting transcripts or "
        "OneDrive files, summarizes decisions and action items, then generates Epics, "
        "Features, and User Stories with proper hierarchy and pushes them to ADO."
    ),
    "procurement-agent": (
        "An autonomous IT procurement agent that manages the full sourcing-to-PO lifecycle "
        "via email, integrated with Oracle Fusion Cloud ERP. Reads requisitions, sends RFQs "
        "to approved suppliers, negotiates counter-offers, validates against procurement "
        "policy, and creates purchase orders in Oracle."
    ),
    "shopping-agent": (
        "A storefront concierge that helps customers browse products, place orders, and "
        "process payments via Stripe MCP. Persists cart and order state in PostgreSQL and "
        "communicates with the user over a WebSocket connection — useful for evaluating "
        "tool-use accuracy and policy adherence around payments."
    ),
}

FRAMEWORKS: dict[str, str] = {
    "bca-agent": "google-adk",
    "card-replacement-agent": "openai-agents-sdk",
    "medical-triage-agent": "google-adk",
    "mini-bcs": "openai-agents-sdk",
    "pm-analyst": "google-adk",
    "procurement-agent": "openai-agents-sdk",
    "shopping-agent": "openai-agents-sdk",
}

LLM_PROVIDERS: dict[str, str] = {
    "bca-agent": "gemini",
    "card-replacement-agent": "openai",
    "medical-triage-agent": "bedrock",
    "mini-bcs": "openai",
    "pm-analyst": "gemini",
    "procurement-agent": "openai",
    "shopping-agent": "openai",
}

ACTORS: dict[str, str] = {
    "bca-agent": "single",
    "card-replacement-agent": "single",
    "medical-triage-agent": "single",
    "mini-bcs": "single",
    "pm-analyst": "single",
    "procurement-agent": "multi",
    "shopping-agent": "single",
}

ARCHITECTURES: dict[str, str] = {
    "bca-agent": "multi-agent",
    "card-replacement-agent": "multi-agent",
    "medical-triage-agent": "single-agent",
    "mini-bcs": "single-agent",
    "pm-analyst": "single-agent",
    "procurement-agent": "single-agent",
    "shopping-agent": "single-agent",
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
        m = SECRET_PATTERN.search(s)
        if m:
            required.add(m.group(1))
        elif PLACEHOLDER_PATTERN.search(s):
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
    its back-compat shims (sandbox#1239) — keeping it here would re-create
    the silent-drop bug that motivated this script.
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


def build_tar(template_dir: Path) -> Path:
    output_path = CONTEXTS_DIR / f"{template_dir.name}.tar.gz"
    subprocess.run(
        ["tar", "-czf", str(output_path), "-C", str(template_dir), "."],
        check=True,
    )
    return output_path


def build_entry(template_dir: Path, env_cfg: dict[str, str]) -> dict:
    template_id = template_dir.name
    raw = yaml.safe_load((template_dir / ".veris" / "veris.yaml").read_text())
    veris_yaml = unwrap_veris_yaml(raw, template_id)

    return {
        "id": template_id,
        "name": DISPLAY_NAMES.get(template_id, template_id),
        "description": DESCRIPTIONS.get(template_id, ""),
        "channel": extract_channel(veris_yaml, template_id),
        "services": extract_services(veris_yaml),
        "framework": FRAMEWORKS.get(template_id),
        "llm_provider": LLM_PROVIDERS.get(template_id),
        "actors": ACTORS.get(template_id),
        "architecture": ARCHITECTURES.get(template_id),
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

    manifest = {"templates": []}
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
