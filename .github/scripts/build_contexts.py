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

# Friendly display names for templates
DISPLAY_NAMES: dict[str, str] = {
    "bca-agent": "Banker Connections Agent",
    "card-replacement-agent": "Card Replacement Agent",
    "mini-bcs": "Bank Customer Service",
    "pm-analyst": "PM Analyst",
    "procurement-agent": "Procurement Agent",
}

# Short UI descriptions (replaces README extraction)
DESCRIPTIONS: dict[str, str] = {
    "bca-agent": "Helps retail bankers resolve customer record update errors in real time using Hogan core banking.",
    "card-replacement-agent": "Handles card freeze, replacement, and activation workflows with PostgreSQL-backed customer data.",
    "mini-bcs": "Credit card support agent with multi-LLM routing and PostgreSQL customer database.",
    "pm-analyst": "Converts meeting transcripts into Azure DevOps work items via Microsoft Graph integration.",
    "procurement-agent": "IT procurement sourcing and negotiation agent with Oracle Fusion Cloud ERP integration.",
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


def extract_description(template_dir: Path) -> str:
    """Extract first paragraph of README as description."""
    readme = template_dir / "README.md"
    if not readme.exists():
        return ""

    lines = readme.read_text().splitlines()
    desc_lines = []
    in_content = False

    for line in lines:
        stripped = line.strip()
        # Skip title lines
        if stripped.startswith("#"):
            if in_content:
                break
            in_content = True
            continue
        # Skip empty lines before content
        if not stripped and not desc_lines:
            continue
        # Stop at empty line after content
        if not stripped and desc_lines:
            break
        if in_content:
            desc_lines.append(stripped)

    return " ".join(desc_lines)[:200]


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

        image_uri = f"{ARTIFACT_REGISTRY}/cookbook-{template_id}:latest" if ARTIFACT_REGISTRY else ""

        entry = {
            "id": template_id,
            "name": DISPLAY_NAMES.get(template_id, template_id),
            "description": DESCRIPTIONS.get(template_id, extract_description(template_dir)),
            "image_uri": image_uri,
            "channel": extract_channel(veris_yaml),
            "services": extract_services(veris_yaml),
            "required_vars": extract_required_vars(veris_yaml, template_dir),
            "veris_yaml": veris_yaml,
        }

        manifest["templates"].append(entry)
        print(f"  channel={entry['channel']}, services={entry['services']}, "
              f"required_vars={entry['required_vars']}, size={tar_size} bytes")

    manifest_path = DIST_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(f"\nGenerated manifest with {len(manifest['templates'])} templates")
    print(f"Output: {DIST_DIR}")


if __name__ == "__main__":
    main()
