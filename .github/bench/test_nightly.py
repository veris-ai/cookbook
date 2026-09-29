import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
import pytest

import nightly

TEMPLATE = {
    "channel_config": {"init": None, "channel": {"type": "http", "url": None}},
    "image": {"port": 8008, "path": "/chat", "health_path": "/health"},
}
IMAGE = "ghcr.io/veris-ai/card-replacement-agent@sha256:" + "a" * 64
CREATE = {"repeats": 1, "parallel": 8, "persona_ids": []}


def make_trial(name="nightly", outdated=False, **extra):
    return {"id": extra.pop("id", "trl_existing"), "name": name, "outdated": outdated,
            "outdated_reasons": ["world"] if outdated else [], "candidate_ids": ["cand_old"],
            "task_ids": ["tsk_1", "tsk_2", "tsk_3"], "repeats": 1, **extra}


class FakeBench:
    """In-memory stand-in for the bench-api routes nightly.py calls."""

    def __init__(self, trials=(), running_polls=0, failure_class=None):
        self.trials = [dict(t) for t in trials]
        self.candidates: list[dict] = []
        self.attempts: dict[str, list[dict]] = {}
        self.calls: list[tuple[str, str, dict | None]] = []
        self.running_polls = running_polls
        self.failure_class = failure_class

    def client(self) -> httpx.Client:
        return nightly.connect("https://bench.test", "vbk_test", httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path.removeprefix("/v1")
        self.calls.append((request.method, path, body))
        parts = path.strip("/").split("/")
        route = (request.method, parts[0], parts[2] if len(parts) > 2 else None)
        if route == ("GET", "benches", "trials"):
            return self.page(self.trials, request)
        if route == ("POST", "benches", "candidates"):
            return httpx.Response(201, json=self.add_candidate(body))
        if route == ("POST", "benches", "trials"):
            trial = {"id": f"trl_{len(self.trials) + 1}", "name": body["name"], "outdated": False,
                     "outdated_reasons": [], "candidate_ids": list(body["candidate_ids"]),
                     "task_ids": ["tsk_1", "tsk_2", "tsk_3"], "repeats": body["repeats"]}
            self.trials.append(trial)
            return httpx.Response(201, json=trial)
        if route == ("POST", "trials", "candidates"):
            trial = self.trial(parts[1])
            trial["candidate_ids"] += body["candidate_ids"]
            return httpx.Response(201, json=trial)
        if route == ("GET", "trials", None):
            return httpx.Response(200, json=self.trial(parts[1]))
        if route == ("GET", "trials", "attempts"):
            items = self.attempts[request.url.params["candidate_id"]]
            if self.running_polls:
                self.running_polls -= 1
                items = [{**a, "status": "running"} for a in items]
            return self.page(items, request)
        if route == ("PUT", "trials", "exclusions"):
            return httpx.Response(204)
        if route == ("GET", "trials", "results"):
            return httpx.Response(200, json={"rollups": [
                {"candidate_id": c["id"], "name": c["name"], "n": 3, "passes": 2, "pending": 0,
                 "pass_rate": 66.7, "ci_low": 20.8, "ci_high": 93.9} for c in self.candidates]})
        return httpx.Response(404, json={"detail": f"no fake route for {request.method} {path}"})

    def add_candidate(self, body: dict) -> dict:
        cid = f"cand_{len(self.candidates) + 1}"
        self.candidates.append({"id": cid, **body})
        self.attempts[cid] = [{"id": f"att_{cid}_{i}", "candidate_id": cid, "status": "completed",
                               "failure_class": None} for i in range(3)]
        if self.failure_class:
            self.attempts[cid][0].update(status="failed", failure_class=self.failure_class)
        return {"id": cid}

    def trial(self, trial_id: str) -> dict:
        return next(t for t in self.trials if t["id"] == trial_id)

    @staticmethod
    def page(items: list[dict], request: httpx.Request) -> httpx.Response:
        limit, offset = int(request.url.params["limit"]), int(request.url.params["offset"])
        return httpx.Response(200, json={"items": items[offset:offset + limit], "total": len(items)})

    def posted(self, method: str, path: str) -> list[dict | None]:
        return [body for m, p, body in self.calls if m == method and p == path]


def test_http_error_names_route_and_body():
    bench = FakeBench()
    with bench.client() as client, pytest.raises(SystemExit, match=r"GET /v1/nowhere -> 404: .*no fake route"):
        client.get("/nowhere")


def test_every_reads_all_pages():
    bench = FakeBench(trials=[make_trial(name=f"t{i}", id=f"trl_{i}") for i in range(450)])
    with bench.client() as client:
        items = nightly.every(client, "/benches/b/trials")
    assert [t["id"] for t in items] == [f"trl_{i}" for i in range(450)]
    assert len(bench.posted("GET", "/benches/b/trials")) == 3


def test_first_night_creates_the_trial():
    bench = FakeBench()
    with bench.client() as client:
        cand, trial = nightly.register(client, "b", "nightly", TEMPLATE, "cr 2026-09-30 (abc1234)", IMAGE, CREATE)
    [candidate] = bench.posted("POST", "/benches/b/candidates")
    assert candidate["name"] == "cr 2026-09-30 (abc1234)"
    assert candidate["image"] == {**TEMPLATE["image"], "ref": IMAGE}
    assert "ref" not in TEMPLATE["image"]
    assert bench.posted("POST", "/benches/b/trials") == [
        {"name": "nightly", "kind": "full", "candidate_ids": [cand], **CREATE}]
    assert trial == bench.trials[0]["id"]


def test_later_night_adds_to_the_named_trial_found_on_a_later_page():
    others = [make_trial(name=f"other {i}", id=f"trl_{i}") for i in range(250)]
    bench = FakeBench(trials=[*others, make_trial(id="trl_nightly")])
    with bench.client() as client:
        cand, trial = nightly.register(client, "b", "nightly", TEMPLATE, "n", IMAGE, CREATE)
    assert trial == "trl_nightly"
    assert bench.posted("POST", "/trials/trl_nightly/candidates") == [{"candidate_ids": [cand]}]
    assert bench.posted("POST", "/benches/b/trials") == []


def test_outdated_trial_refuses_before_creating_a_candidate():
    bench = FakeBench(trials=[make_trial(outdated=True)])
    with bench.client() as client, pytest.raises(SystemExit, match=r"outdated \(world\).*change --trial"):
        nightly.register(client, "b", "nightly", TEMPLATE, "n", IMAGE, CREATE)
    assert bench.candidates == []


def test_two_trials_with_the_name_refuse():
    bench = FakeBench(trials=[make_trial(id="trl_a"), make_trial(id="trl_b")])
    with bench.client() as client, pytest.raises(SystemExit, match="2 trials are named 'nightly'"):
        nightly.register(client, "b", "nightly", TEMPLATE, "n", IMAGE, CREATE)
    assert bench.candidates == []
