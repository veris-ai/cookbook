#!/usr/bin/env python3
"""Apply a Veris report's agent-fixes to the agent source and emit a PR body.

Input is the JSON from `veris reports get <rpt_id> --format json` (the backend's
/agent-fixes payload):

    {"report_id": "...", "status": "completed",
     "fixes": [{"route": "skill"|"system_prompt"|"tool_schema",
                "confidence": "low"|"medium"|"high",
                "target_path": "skills/.../SKILL.md",   # relative to the agent root
                "diff": "diff --git a/skills/... b/skills/...\n...",
                "title": ..., "description": ..., "issue_name": ...,
                "simulations_affected": [...]}, ...]}

Each fix's `diff` is a git diff whose paths are relative to the agent root, so we
`git apply --directory=<agent-dir> -p1` to land it under <agent-dir>/. The
/agent-fixes endpoint already returns only AGENT_FIXABLE routes; we re-check
defensively. Fixes that don't apply cleanly are reported in the PR body, not
forced — a drifted baseline is a signal for a human, not something to fuzz over.

Exit codes (so the caller can tell "clean" from "drifted"):
  0 — >=1 fix applied; caller opens a draft PR.
  2 — agent-fixable fixes were found but ALL failed to apply (baseline drift);
      nothing to PR, but the caller should surface the PR body, not call it clean.
  1 — nothing agent-fixable at all (a genuinely clean run).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Routes the report marks as safe to apply to agent source (mirrors the backend's
# AGENT_FIXABLE_ROUTES). bad_scenario / capability findings are parked, not ingested.
AGENT_FIXABLE = {"skill", "system_prompt", "tool_schema"}


def _git_apply(repo_root: Path, agent_dir: str, diff: str) -> tuple[bool, str]:
    """git apply the diff under agent_dir. --recount tolerates stale hunk line
    numbers (the diff was cut against the deployed file) as long as context matches."""
    text = diff if diff.endswith("\n") else diff + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as fh:
        fh.write(text)
        patch = fh.name
    try:
        r = subprocess.run(
            ["git", "apply", "--directory", agent_dir, "-p1", "--recount", patch],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        return r.returncode == 0, r.stderr.strip()
    finally:
        Path(patch).unlink(missing_ok=True)


def _fix_md(status: str, fix: dict, err: str = "") -> list[str]:
    sims = ", ".join(fix.get("simulations_affected") or []) or "—"
    out = [
        f"### {status}: {fix.get('title') or fix.get('issue_name') or 'fix'}",
        f"- **route:** `{fix.get('route')}` · **confidence:** {fix.get('confidence')} "
        f"· **target:** `{fix.get('target_path')}`",
        f"- **sims affected:** {sims}",
    ]
    if fix.get("description"):
        out += ["", fix["description"], ""]
    if err:
        out += ["", f"> apply error: `{err}`", ""]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixes", required=True, help="agent-fixes JSON (veris reports get --format json)")
    ap.add_argument("--agent-dir", default="crm-analyst-agent", help="agent root, relative to repo")
    ap.add_argument("--repo-root", default=".", help="git repo root to apply within")
    ap.add_argument("--pr-body", default="pr_body.md", help="path to write the PR body markdown")
    args = ap.parse_args()

    payload = json.loads(Path(args.fixes).read_text())
    report_id = payload.get("report_id", "?")
    fixes = payload.get("fixes") or []
    repo_root = Path(args.repo_root).resolve()

    applied: list[tuple[dict, str]] = []
    failed: list[tuple[dict, str]] = []
    skipped: list[tuple[dict, str]] = []

    for fix in fixes:
        route = fix.get("route")
        if route not in AGENT_FIXABLE:
            skipped.append((fix, f"route '{route}' not agent-fixable"))
            continue
        diff = fix.get("diff") or ""
        if not diff.strip():
            failed.append((fix, "empty diff"))
            continue
        ok, err = _git_apply(repo_root, args.agent_dir, diff)
        (applied if ok else failed).append((fix, err))

    body = [
        f"## Agent-fix ingestion from report `{report_id}`",
        "",
        f"Auto-applied **{len(applied)}** agent-fixable suggestion(s) from a Veris "
        "simulation report. Each diff changes the agent's SOUL / skills / tool schemas — "
        "**review before merging.**",
        "",
    ]
    for fix, _ in applied:
        body += _fix_md("✅ Applied", fix)
    if failed:
        body += ["", "### ⚠️ Could not auto-apply (baseline drift — apply by hand)", ""]
        for fix, err in failed:
            body += _fix_md("❌ Failed", fix, err)
    if skipped:
        body += ["", f"_Skipped {len(skipped)} non-agent-fixable finding(s)._"]
    Path(args.pr_body).write_text("\n".join(body) + "\n")

    print(f"applied={len(applied)} failed={len(failed)} skipped={len(skipped)}", file=sys.stderr)
    if applied:
        return 0
    if failed:
        return 2  # agent-fixable fixes found but none applied — baseline drift, surface it
    return 1  # nothing agent-fixable


if __name__ == "__main__":
    raise SystemExit(main())
