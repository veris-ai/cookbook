# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Add tonight's image to a long-lived bench trial as a new candidate, wait for it, chart the trial.

Three parts, in order: register (candidate + find-or-create the trial by name + add),
wait (poll the candidate's attempts), report (exclude platform failures, read the
trial's rollups, write results.json and chart.svg, set the exit code).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

PAGE = 200
POLL_S = 60
WAIT_LIMIT_S = 3 * 60 * 60
IN_FLIGHT = {"pending", "running"}


def fail(message: str) -> SystemExit:
    return SystemExit(f"nightly: {message}")


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_error:
        response.read()
        raise fail(f"{response.request.method} {response.request.url.path} -> "
                   f"{response.status_code}: {response.text}")


def connect(api: str, key: str, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        base_url=f"{api.rstrip('/')}/v1",
        headers={"Authorization": f"Bearer {key}"},
        timeout=60,
        transport=transport,
        event_hooks={"response": [_raise_for_status]},
    )


def every(client: httpx.Client, path: str, **params: str) -> list[dict]:
    """Every item of a paged bench-api list."""
    items: list[dict] = []
    while True:
        page = client.get(path, params={**params, "limit": PAGE, "offset": len(items)}).json()
        items += page["items"]
        if not page["items"] or len(items) >= page["total"]:
            return items


def candidate_name(label: str, day: str, sha: str) -> str:
    return f"{label} {day} ({sha})"


def register(client: httpx.Client, bench: str, trial_name: str, template: dict, name: str,
             image: str, create: dict) -> tuple[str, str]:
    """Create tonight's candidate and put it in the trial named `trial_name`.

    The trial is resolved first, so a refused night leaves no orphan candidate. A trial
    whose roster lost a candidate refuses the add itself (409), which `connect` reports.
    """
    matches = [t for t in every(client, f"/benches/{bench}/trials") if t["name"] == trial_name]
    if len(matches) > 1:
        raise fail(f"{len(matches)} trials are named {trial_name!r}; point --trial at a unique name")
    if matches and matches[0]["outdated"]:
        reasons = ", ".join(matches[0]["outdated_reasons"])
        raise fail(f"trial {matches[0]['id']} is outdated ({reasons}): the bench changed; "
                   "change --trial to start a new series")
    # An edit never outdates a trial on its own: new attempts would silently run the new text.
    if matches and (edited := matches[0]["edited_task_ids"] + matches[0]["stale_persona_ids"]):
        raise fail(f"trial {matches[0]['id']} has tasks or archetypes edited since it ran "
                   f"({', '.join(edited)}): change --trial to start a new series")
    body = {**template, "name": name, "image": {**template["image"], "ref": image}}
    candidate = client.post(f"/benches/{bench}/candidates", json=body).json()["id"]
    if matches:
        trial = matches[0]["id"]
        client.post(f"/trials/{trial}/candidates", json={"candidate_ids": [candidate]})
        return candidate, trial
    created = client.post(f"/benches/{bench}/trials", json={
        "name": trial_name, "kind": "full", "candidate_ids": [candidate], **create}).json()
    return candidate, created["id"]


def wait(client: httpx.Client, trial: str, candidate: str,
         clock: Callable[[], float] = time.monotonic,
         sleep: Callable[[float], None] = time.sleep) -> tuple[list[dict], bool]:
    """Poll the candidate's attempts until none is in flight. Returns (attempts, finished).

    Polling is what moves the trial: bench-api has no scheduler, and these reads time
    out dead attempts and top up the dispatch queue.
    """
    deadline = clock() + WAIT_LIMIT_S
    while True:
        attempts = every(client, f"/trials/{trial}/attempts", candidate_id=candidate)
        if attempts and not any(a["status"] in IN_FLIGHT for a in attempts):
            return attempts, True
        if clock() >= deadline:
            return attempts, False
        sleep(POLL_S)


def exclude_platform_failures(client: httpx.Client, trial: str) -> list[str]:
    """Leave Veris-side failures out of the pass rate, across the whole trial.

    Trial-wide, so attempts that settled after an earlier night's run gave up (or died)
    are caught on the next night. The run still ends red for tonight's failures.
    """
    ids = [a["id"] for a in every(client, f"/trials/{trial}/attempts", status="failed")
           if a["failure_class"] == "platform" and a["excluded_reason"] is None]
    if ids:
        client.put(f"/trials/{trial}/exclusions", json={"attempt_ids": ids, "reason": "platform failure"})
    return ids


def rows(results: dict, trial: dict, label: str) -> list[dict]:
    """One row per nightly candidate in the trial, in the order they joined it."""
    pattern = re.compile(rf"{re.escape(label)} (\d{{4}}-\d{{2}}-\d{{2}}) \(([0-9a-f]+)\)")
    # "every" casting runs each task once per archetype; "split" deals one archetype per task.
    casts = len(trial["persona_ids"]) if trial["casting"] == "every" and trial["persona_ids"] else 1
    expected = len(trial["task_ids"]) * trial["repeats"] * casts
    out = []
    for r in results["rollups"]:
        match = pattern.fullmatch(r["name"])
        if not match:
            continue
        out.append({
            "date": match[1], "sha": match[2], "candidate_id": r["candidate_id"],
            "pass_rate": r["pass_rate"] if r["n"] else None,
            "ci_low": r["ci_low"], "ci_high": r["ci_high"],
            "n": r["n"], "passes": r["passes"], "expected": expected,
        })
    return sorted(out, key=lambda row: trial["candidate_ids"].index(row["candidate_id"]))


WIDTH, HEIGHT = 760, 320
LEFT, RIGHT, TOP, BOTTOM = 48, 24, 60, 40
STYLE = """
.grid{stroke:#d0d7de} .axis,.sub{fill:#57606a;font:12px sans-serif} .title{fill:#1f2328;font:600 14px sans-serif}
.band{stroke:#1a7f64;stroke-width:3;opacity:.35} .line{fill:none;stroke:#1a7f64;stroke-width:1.5}
.dot{fill:#1a7f64} .hollow{fill:#ffffff;stroke:#1a7f64;stroke-width:2}
@media (prefers-color-scheme: dark){
  .grid{stroke:#30363d} .axis,.sub{fill:#8b949e} .title{fill:#e6edf3}
  .band,.line{stroke:#3fb68b} .dot{fill:#3fb68b} .hollow{fill:#0d1117;stroke:#3fb68b}
}"""


def render_svg(rows: list[dict], title: str, updated: str) -> str:
    """Pass rate per night with its 95% interval; hollow where some attempts did not count."""
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    step = plot_w / max(len(rows), 1)

    def x(i: int) -> float:
        return LEFT + step * (i + 0.5)

    def y(value: float) -> float:
        return TOP + plot_h * (1 - value / 100)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="{html.escape(title)}">',
        f"<style>{STYLE}</style>",
        f'<text class="title" x="{LEFT}" y="24">{html.escape(title)}</text>',
        f'<text class="sub" x="{LEFT}" y="42">updated {html.escape(updated)}</text>',
    ]
    for value in (0, 50, 100):
        out.append(f'<line class="grid" x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y(value):.1f}" y2="{y(value):.1f}"/>')
        out.append(f'<text class="axis" x="{LEFT - 8}" y="{y(value) + 4:.1f}" text-anchor="end">{value}</text>')
    judged = [(i, r) for i, r in enumerate(rows) if r["pass_rate"] is not None]
    if len(judged) > 1:
        points = " ".join(f"{x(i):.1f},{y(r['pass_rate']):.1f}" for i, r in judged)
        out.append(f'<polyline class="line" points="{points}"/>')
    for i, r in judged:
        hollow = r["n"] < r["expected"]
        tip = f"{r['date']} ({r['sha']}): {r['passes']}/{r['n']} passed, {r['pass_rate']:.0f}%"
        out.append(f'<line class="band" x1="{x(i):.1f}" x2="{x(i):.1f}" '
                   f'y1="{y(r["ci_low"]):.1f}" y2="{y(r["ci_high"]):.1f}"/>')
        out.append(f'<circle class="{"hollow" if hollow else "dot"}" cx="{x(i):.1f}" '
                   f'cy="{y(r["pass_rate"]):.1f}" r="4.5"><title>{html.escape(tip)}</title></circle>')
        if hollow:
            out.append(f'<text class="axis" x="{x(i) + 7:.1f}" y="{y(r["pass_rate"]) - 7:.1f}">'
                       f'{r["n"]}/{r["expected"]}</text>')
    label_every = max(1, -(-len(rows) // 10))
    for i, r in enumerate(rows):
        if i % label_every == 0 or i == len(rows) - 1:
            out.append(f'<text class="axis" x="{x(i):.1f}" y="{HEIGHT - 16}" '
                       f'text-anchor="middle">{r["date"][5:]}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def summary(row: dict | None, trial_url: str, failed: list[dict], finished: bool) -> str:
    platform = sum(a["failure_class"] == "platform" for a in failed)
    lines = ["## Nightly bench run", ""]
    if row and row["pass_rate"] is not None:
        lines.append(f"**Tonight:** {row['pass_rate']:.0f}% ({row['passes']}/{row['n']} passed; "
                     f"95% interval {row['ci_low']:.0f}–{row['ci_high']:.0f})")
    else:
        lines.append("**Tonight:** no judged attempts")
    if not finished:
        lines.append(f"- Still running after {WAIT_LIMIT_S // 3600} h; the next run's chart picks up the rest.")
    if failed:
        lines.append(f"- {len(failed)} attempt(s) failed ({platform} platform, excluded from the pass rate).")
    lines.append(f"- [Trial on bench]({trial_url})")
    return "\n".join(lines) + "\n"


def parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bench", required=True, help="bench id")
    p.add_argument("--trial", required=True, help="trial name; created on the first run")
    p.add_argument("--label", required=True, help="candidate name prefix and results folder")
    p.add_argument("--candidate", required=True, type=Path, help="candidate template JSON")
    p.add_argument("--image", required=True, help="image ref pinned by digest")
    p.add_argument("--sha", required=True, help="short git sha of the build")
    p.add_argument("--out", required=True, type=Path, help="directory for results.json and chart.svg")
    p.add_argument("--repeats", type=int, default=1, help="used only when the trial is created")
    p.add_argument("--parallel", type=int, default=8, help="used only when the trial is created")
    p.add_argument("--personas", choices=["none", "all"], default="none",
                   help="used only when the trial is created: none runs the bare tasks")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, transport: httpx.BaseTransport | None = None,
         clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
         now: datetime | None = None) -> int:
    args = parse(argv)
    if "@sha256:" not in args.image:
        raise fail(f"--image must be pinned by digest, got {args.image!r}")
    api, key, console = os.environ["BENCH_API"], os.environ["BENCH_API_KEY"], os.environ["BENCH_CONSOLE"]
    now = now or datetime.now(timezone.utc)
    template = json.loads(args.candidate.read_text())
    create = {"repeats": args.repeats, "parallel": args.parallel}
    if args.personas == "none":
        create["persona_ids"] = []

    with connect(api, key, transport) as client:
        name = candidate_name(args.label, now.date().isoformat(), args.sha)
        candidate, trial_id = register(client, args.bench, args.trial, template, name, args.image, create)
        attempts, finished = wait(client, trial_id, candidate, clock, sleep)
        return report(client, trial_id, candidate, attempts, finished, args.label, args.out,
                      f"{console.rstrip('/')}/benchmarks/{args.bench}?trial={trial_id}", now)


def report(client: httpx.Client, trial_id: str, candidate: str, attempts: list[dict], finished: bool,
           label: str, out: Path, trial_url: str, now: datetime) -> int:
    """Exclude platform failures, chart the whole trial, write the job summary. Returns the exit code."""
    exclude_platform_failures(client, trial_id)
    trial = client.get(f"/trials/{trial_id}").json()
    results = client.get(f"/trials/{trial_id}/results").json()

    data = rows(results, trial, label)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(data, indent=2) + "\n")
    repeats = trial["repeats"]
    title = (f"{label} · {len(trial['task_ids'])} tasks × {repeats} repeat{'s' if repeats != 1 else ''}"
             " · bars = 95% interval")
    (out / "chart.svg").write_text(render_svg(data, title, now.strftime("%Y-%m-%d %H:%M UTC")))

    failed = [a for a in attempts if a["status"] == "failed"]
    tonight = next((r for r in data if r["candidate_id"] == candidate), None)
    text = summary(tonight, trial_url, failed, finished)
    print(text)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a") as f:
            f.write(text)
    return 0 if finished and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
