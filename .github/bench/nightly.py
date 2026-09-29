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

import httpx

PAGE = 200


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
    body = {**template, "name": name, "image": {**template["image"], "ref": image}}
    candidate = client.post(f"/benches/{bench}/candidates", json=body).json()["id"]
    if matches:
        trial = matches[0]["id"]
        client.post(f"/trials/{trial}/candidates", json={"candidate_ids": [candidate]})
        return candidate, trial
    created = client.post(f"/benches/{bench}/trials", json={
        "name": trial_name, "kind": "full", "candidate_ids": [candidate], **create}).json()
    return candidate, created["id"]
