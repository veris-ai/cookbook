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


def test_wait_polls_until_nothing_is_in_flight():
    bench = FakeBench(running_polls=2)
    bench.add_candidate({"name": "n"})
    sleeps = []
    with bench.client() as client:
        attempts, finished = nightly.wait(client, "trl_1", "cand_1", clock=lambda: 0.0, sleep=sleeps.append)
    assert finished and len(attempts) == 3
    assert sleeps == [nightly.POLL_S, nightly.POLL_S]


def test_wait_gives_up_after_the_limit():
    bench = FakeBench(running_polls=10**6)
    bench.add_candidate({"name": "n"})
    ticks = iter([0.0, nightly.WAIT_LIMIT_S + 1])
    with bench.client() as client:
        attempts, finished = nightly.wait(client, "trl_1", "cand_1", clock=lambda: next(ticks), sleep=lambda s: None)
    assert not finished
    assert {a["status"] for a in attempts} == {"running"}


def test_only_platform_failures_are_excluded():
    attempts = [
        {"id": "a1", "status": "failed", "failure_class": "platform"},
        {"id": "a2", "status": "failed", "failure_class": "candidate"},
        {"id": "a3", "status": "failed", "failure_class": "unknown"},
        {"id": "a4", "status": "completed", "failure_class": None},
    ]
    bench = FakeBench()
    with bench.client() as client:
        assert nightly.exclude_platform_failures(client, "trl_1", attempts) == ["a1"]
    assert bench.posted("PUT", "/trials/trl_1/exclusions") == [{"attempt_ids": ["a1"], "reason": "platform failure"}]


def test_no_exclusion_call_without_platform_failures():
    bench = FakeBench()
    with bench.client() as client:
        assert nightly.exclude_platform_failures(
            client, "trl_1", [{"id": "a", "status": "completed", "failure_class": None}]) == []
    assert bench.calls == []


def rollup(cid, name, n=25, passes=18, pass_rate=72.0):
    return {"candidate_id": cid, "name": name, "n": n, "passes": passes, "pending": 0,
            "pass_rate": pass_rate, "ci_low": 52.4, "ci_high": 85.7}


def test_rows_keep_nightly_candidates_in_roster_order():
    trial = make_trial(candidate_ids=["c3", "c1", "smoke", "c2"], task_ids=[f"t{i}" for i in range(25)])
    results = {"rollups": [
        rollup("c1", "card-replacement 2026-09-30 (abc1234)"),
        rollup("c2", "card-replacement 2026-10-01 (def5678)"),
        rollup("smoke", "hand-made smoke test"),
        rollup("c3", "card-replacement 2026-09-30 (0f0f0f0)"),
    ]}
    data = nightly.rows(results, trial, "card-replacement")
    assert [r["candidate_id"] for r in data] == ["c3", "c1", "c2"]
    assert data[1] == {"date": "2026-09-30", "sha": "abc1234", "candidate_id": "c1", "pass_rate": 72.0,
                       "ci_low": 52.4, "ci_high": 85.7, "n": 25, "passes": 18, "expected": 25}


def test_rows_treat_zero_judged_attempts_as_missing():
    trial = make_trial(candidate_ids=["c1"])
    results = {"rollups": [rollup("c1", "cr 2026-09-30 (abc1234)", n=0, passes=0, pass_rate=0.0)]}
    assert nightly.rows(results, trial, "cr")[0]["pass_rate"] is None


def test_rows_match_labels_with_regex_characters_literally():
    trial = make_trial(candidate_ids=["c1", "c2"])
    results = {"rollups": [rollup("c1", "a.b 2026-09-30 (abc1234)"), rollup("c2", "axb 2026-09-30 (abc1234)")]}
    assert [r["candidate_id"] for r in nightly.rows(results, trial, "a.b")] == ["c1"]


def row(pass_rate=72.0, n=25, expected=25):
    return {"date": "2026-09-30", "sha": "abc1234", "candidate_id": "c", "pass_rate": pass_rate,
            "ci_low": 52.4, "ci_high": 85.7, "n": n, "passes": 18, "expected": expected}


SVG = {"s": "http://www.w3.org/2000/svg"}


def test_svg_draws_a_point_per_judged_night():
    svg = nightly.render_svg([row(), row(n=23, pass_rate=78.3), row(pass_rate=None, n=0)], "t", "now")
    root = ET.fromstring(svg)
    assert [c.get("class") for c in root.findall(".//s:circle", SVG)] == ["dot", "hollow"]
    assert "23/25" in svg
    assert len(root.findall(".//s:polyline", SVG)) == 1


def test_svg_with_no_rows_is_still_valid():
    ET.fromstring(nightly.render_svg([], "t", "now"))


def test_svg_escapes_the_title():
    svg = nightly.render_svg([row()], "R&D <agent>", "now")
    ET.fromstring(svg)
    assert "R&amp;D &lt;agent&gt;" in svg
