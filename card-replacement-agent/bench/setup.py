# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Create the card-replacement bench once per environment: bench, world, 25 tasks, OPENAI_API_KEY.

Needs BENCH_API, BENCH_API_KEY and OPENAI_API_KEY in the environment, and a twin environment
plus snapshot made with the veris CLI (see ../README.md, "Nightly benchmark"). Prints the bench id.
"""
import argparse
import json
import os
from pathlib import Path

import httpx


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--name", required=True, help="bench name")
    p.add_argument("--env-id", required=True, help="twin environment id (veris env get)")
    p.add_argument("--snapshot-id", required=True, help="twin snapshot id (veris snapshot create)")
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    args = p.parse_args()
    tasks = json.loads(args.tasks.read_text())
    openai_key = os.environ["OPENAI_API_KEY"]
    with httpx.Client(base_url=f"{os.environ['BENCH_API'].rstrip('/')}/v1",
                      headers={"Authorization": f"Bearer {os.environ['BENCH_API_KEY']}"}, timeout=60) as client:

        def call(method: str, path: str, body: dict) -> dict | None:
            r = client.request(method, path, json=body)
            if r.is_error:
                raise SystemExit(f"setup: {method} {path} -> {r.status_code}: {r.text}")
            return r.json() if r.content else None

        bench = call("POST", "/benches", {
            "name": args.name,
            "description": "Nightly CI example: veris-ai/cookbook card-replacement-agent"})["id"]
        call("POST", f"/benches/{bench}/worlds", {
            "name": "card-replacement postgres",
            "services": [{"binding_id": "postgres", "service": "postgres",
                          "dataset_ref": f"{args.env_id}/{args.snapshot_id}"}]})
        for task in tasks:
            call("POST", f"/benches/{bench}/tasks", task)
        call("PUT", f"/benches/{bench}/candidate-env/OPENAI_API_KEY", {"value": openai_key, "is_secret": True})
    print(bench)


if __name__ == "__main__":
    main()
