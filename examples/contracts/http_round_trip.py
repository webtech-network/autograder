"""Executable HTTP validate/create/submit/poll example for the static definition."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx


DEFINITION = (
    Path(__file__).resolve().parents[2]
    / "docs/contracts/v1/examples/static-conformance.json"
)


async def round_trip(client: httpx.AsyncClient, assignment_id: str) -> dict:
    definition = json.loads(DEFINITION.read_text(encoding="utf-8"))
    validated = await client.post("/api/v1/configs/validate", json=definition)
    validated.raise_for_status()
    created = await client.post(
        "/api/v1/configs",
        json={"external_assignment_id": assignment_id, "definition": definition},
    )
    created.raise_for_status()
    assert created.json()["definition_hash"] == validated.json()["definition_hash"]

    submitted = await client.post(
        "/api/v1/submissions",
        json={
            "external_assignment_id": assignment_id,
            "external_user_id": "walkthrough-student",
            "username": "Walkthrough Student",
            "files": [{"filename": "index.html", "content": "<h1>Hello</h1>"}],
        },
    )
    submitted.raise_for_status()
    assert submitted.status_code == 202
    status_url = submitted.headers["Location"]
    submission_id = submitted.json()["id"]
    for _ in range(100):
        polled = await client.get(status_url)
        polled.raise_for_status()
        result = polled.json()
        if result["status"] in ("completed", "failed"):
            return result
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Submission {submission_id} did not finish within five seconds")


async def main(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        result = await round_trip(client, f"walkthrough-{uuid4().hex}")
    print(json.dumps(result, indent=2))
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    asyncio.run(main(parser.parse_args().base_url))
