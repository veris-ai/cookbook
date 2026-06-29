"""End-to-end test for ingest_report.py: a real agent-fixes payload is applied to
a temp git repo via `git apply`, and a PR body is emitted.

The target file's pre-image is derived from the diff's own context lines (the
example fix is a pure insertion), so the test stays faithful to the real format
without committing a full copy of the deployed skill.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "ingest_report.py"
_FIXTURE = _HERE / "fixtures" / "agent_fixes_example.json"


def _preimage_from_diff(diff: str) -> str:
    """Reconstruct the file the diff applies to, from its context lines (works for
    a pure-insertion hunk: context lines = the original file)."""
    out, in_hunk = [], False
    for line in diff.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+"):
            continue  # added line — not in the pre-image
        out.append(line[1:] if line.startswith(" ") else line)  # strip context marker
    return "\n".join(out) + "\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_applies_skill_fix_and_skips_non_agent_fixable(tmp_path):
    payload = json.loads(_FIXTURE.read_text())
    skill_fix = next(f for f in payload["fixes"] if f["route"] == "skill")

    repo = tmp_path
    target = repo / "crm-analyst-agent" / skill_fix["target_path"]
    target.parent.mkdir(parents=True)
    target.write_text(_preimage_from_diff(skill_fix["diff"]))

    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")

    fixes = repo / "fixes.json"
    fixes.write_text(json.dumps(payload))
    pr_body = repo / "pr_body.md"

    r = subprocess.run(
        [
            sys.executable, str(_SCRIPT),
            "--fixes", str(fixes),
            "--repo-root", str(repo),
            "--agent-dir", "crm-analyst-agent",
            "--pr-body", str(pr_body),
        ],
        capture_output=True, text=True,
    )

    assert r.returncode == 0, r.stderr
    # the inserted line landed in the right file
    assert "STILL a valid approval" in target.read_text()
    # PR body reports the applied skill fix and skips the parked bad_scenario
    body = pr_body.read_text()
    assert "✅ Applied" in body
    assert "skills/nemo-sales-crm-approval/SKILL.md" in body
    assert "Skipped 1 non-agent-fixable" in body
    assert "applied=1" in r.stderr and "skipped=1" in r.stderr


def test_exits_1_when_nothing_agent_fixable(tmp_path):
    # only a non-agent-fixable finding → nothing applied, nothing failed → exit 1 (clean)
    payload = {"report_id": "rpt_x", "fixes": [
        {"route": "capability", "diff": "", "target_path": None, "title": "x"}
    ]}
    fixes = tmp_path / "fixes.json"
    fixes.write_text(json.dumps(payload))
    repo = tmp_path
    _git(repo, "init", "-q")
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--fixes", str(fixes), "--repo-root", str(repo),
         "--pr-body", str(tmp_path / "pr.md")],
        capture_output=True, text=True,
    )
    assert r.returncode == 1, r.stderr


def test_exits_2_when_agent_fixable_but_all_fail(tmp_path):
    # an agent-fixable fix whose diff cannot apply (target file absent) → exit 2,
    # and the PR body still records it under the baseline-drift section.
    payload = {"report_id": "rpt_y", "fixes": [{
        "route": "skill",
        "target_path": "skills/missing/SKILL.md",
        "title": "drifted fix",
        "diff": (
            "diff --git a/skills/missing/SKILL.md b/skills/missing/SKILL.md\n"
            "--- a/skills/missing/SKILL.md\n"
            "+++ b/skills/missing/SKILL.md\n"
            "@@ -1,1 +1,2 @@\n"
            " a line that does not exist in any file\n"
            "+inserted\n"
        ),
    }]}
    fixes = tmp_path / "fixes.json"
    fixes.write_text(json.dumps(payload))
    repo = tmp_path
    _git(repo, "init", "-q")
    pr_body = tmp_path / "pr.md"
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--fixes", str(fixes), "--repo-root", str(repo),
         "--agent-dir", "crm-analyst-agent", "--pr-body", str(pr_body)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2, r.stderr
    assert "applied=0 failed=1" in r.stderr
    assert "Could not auto-apply" in pr_body.read_text()
