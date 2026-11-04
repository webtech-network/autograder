#!/usr/bin/env python3
"""Capacity benchmark for an already running Autograder HTTP stack.

The benchmark never starts, migrates or configures the stack. It talks to the
public HTTP API with an integration token, so it measures the same path an
integrator uses: real HTTP, the durable PostgreSQL queue, workers and sandboxes.

    python scripts/capacity_benchmark.py --url http://localhost:8000 \\
        --workload python-io --submissions 200 > result.json

Each run fires one burst of concurrent ``POST /api/v1/submissions`` requests
(plus concurrent ``POST /api/v1/execute`` calls for ``--workload mix``), polls
the run's history until every accepted submission is terminal, and reports
acceptance latency, drain rate, failures by code, queue wait, grading duration,
peak sandboxes, API RSS, leftover sandbox containers and the hardware.

Metrics are printed as JSON on stdout and a short summary on stderr. The exit
status gates correctness only, never timing:

* 0  every submission was accepted and reached a terminal state, and no failure
     code outside ``--allow-failure`` appeared;
* 1  some submission was rejected, never terminated before ``--timeout``,
     failed with an unexpected code, or a deliberate execution returned a status
     other than 200 or a defined saturation status (429/503);
* 2  the stack is not ready or the benchmark configuration could not be set up.

Configurations are upserted under fixed aliases (``capacity-benchmark-<kind>``)
and deactivated afterwards, so repeated runs reuse two resources instead of
creating new ones. Submissions are durable history by design; every run uses a
distinct ``external_user_id`` (``capacity-benchmark-<run id>``).

See docs/contracts/JOBS.md for the reference result and how to read it.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import os
import platform
import statistics
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

EXAMPLES = Path(__file__).resolve().parents[1] / "docs" / "contracts" / "v1" / "examples"
WORKLOADS = ("python-io", "webdev", "mix")
ALIASES = {"python-io": "capacity-benchmark-python-io", "webdev": "capacity-benchmark-webdev"}
TERMINAL = ("completed", "failed")
# Deliberate execution answers 200, or a defined saturation status (PRF-01).
EXPECTED_EXECUTION_STATUSES = {200, 429, 503}
SANDBOX_APP_LABEL = "autograder.sandbox.app=autograder-sandbox"
WEB_TAGS = ("h1", "h2", "p", "ul", "li", "a", "section", "header", "footer", "nav",
            "main", "article", "table", "tr", "td", "form", "label", "button", "span", "em")
API = "/api/v1"


class SetupError(RuntimeError):
    """The stack cannot run the benchmark (not ready, unauthorized, rejected config)."""


# ---------------------------------------------------------------- workloads
def _example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _with_tests(definition, tests):
    definition = copy.deepcopy(definition)
    definition["criteria"]["base"]["tests"] = tests
    return definition


def python_io_definition(tests):
    """The checked-in python-io example with ``tests`` distinct stdin/stdout cases."""
    definition = _example("python-io.json")
    template = definition["criteria"]["base"]["tests"][0]
    cases = []
    for index in range(tests):
        case = copy.deepcopy(template)
        case.update(id=f"io-{index}", name=f"Sum {index}", weight=1.0)
        case["parameters"].update(inputs=[str(index), "20"], expected_output=str(index + 20))
        cases.append(case)
    return _with_tests(definition, cases)


def webdev_definition(criteria):
    """The checked-in webdev example with ``criteria`` has_tag checks over one page."""
    definition = _example("webdev.json")
    template = definition["criteria"]["base"]["tests"][0]
    checks = []
    for index in range(criteria):
        check = copy.deepcopy(template)
        tag = WEB_TAGS[index % len(WEB_TAGS)]
        check.update(id=f"tag-{index}", name=f"Has {tag} ({index})", weight=1.0)
        check["parameters"].update(tag=tag, required_count=1)
        checks.append(check)
    return _with_tests(definition, checks)


def python_io_files(nonce):
    """A correct program, distinct per submission so nothing can be shared by accident."""
    return [{"filename": "main.py",
             "content": f"# capacity benchmark {nonce}\na = int(input())\nb = int(input())\nprint(a + b)\n"}]


def webdev_files(nonce, page_kb):
    """A correct page containing every checked tag, padded to about ``page_kb`` KiB."""
    tags = "".join(f"<{tag}>{tag} {nonce}</{tag}>" for tag in WEB_TAGS)
    head = f"<!doctype html><html><head><title>{nonce}</title></head><body><h1>{nonce}</h1>{tags}"
    filler, size = [], len(head)
    target = page_kb * 1024
    while size < target:
        paragraph = f"<p>Benchmark page {nonce}, paragraph {len(filler)}: unique filler text.</p>"
        filler.append(paragraph)
        size += len(paragraph)
    return [{"filename": "index.html", "content": head + "".join(filler) + "</body></html>"}]


def execution_request(nonce):
    """One small deliberate run, sharing the sandbox pools with grading."""
    return {"language": "python", "program_command": "python3 main.py", "test_cases": [["1", "2"]],
            "submission_files": python_io_files(nonce)}


def plan(args):
    """Definitions per alias and the (alias, files) of every submission in one burst."""
    kinds = ["python-io", "webdev"] if args.workload == "mix" else [args.workload]
    definitions = {ALIASES["python-io"]: python_io_definition(args.tests)} if "python-io" in kinds else {}
    if "webdev" in kinds:
        definitions[ALIASES["webdev"]] = webdev_definition(args.criteria)

    def submissions(run_id):
        for index in range(args.submissions):
            kind = kinds[index % len(kinds)]
            nonce = f"{run_id}-{index}"
            files = python_io_files(nonce) if kind == "python-io" else webdev_files(nonce, args.page_kb)
            yield ALIASES[kind], files
    return definitions, submissions


# ---------------------------------------------------------------- statistics
def percentiles(values):
    """Nearest-rank summary in seconds, or None for an empty sample."""
    values = sorted(values)
    if not values:
        return None

    def rank(fraction):
        return values[max(0, math.ceil(len(values) * fraction) - 1)]
    return {"count": len(values), "min": round(values[0], 3), "p50": round(rank(0.50), 3),
            "p95": round(rank(0.95), 3), "p99": round(rank(0.99), 3), "max": round(values[-1], 3)}


def _timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def variance(runs):
    """Min/median/max of the headline metrics across repeated runs."""
    def pick(run, path):
        for key in path:
            run = run.get(key) if isinstance(run, dict) else None
        return run
    metrics = {
        "acceptance_p95_seconds": ("acceptance", "latency_seconds", "p95"),
        "drain_seconds": ("drain", "seconds"),
        "gradings_per_minute": ("drain", "gradings_per_minute"),
        "queue_wait_p95_seconds": ("queue_wait_seconds", "p95"),
        "grading_duration_p50_seconds": ("grading_duration_seconds", "p50"),
        "peak_sandboxes": ("sandboxes", "peak"),
        "peak_api_rss_mb": ("api_rss_mb", "peak"),
    }
    result = {}
    for name, path in metrics.items():
        values = [value for value in (pick(run, path) for run in runs) if value is not None]
        if values:
            result[name] = {"min": min(values), "median": statistics.median(values), "max": max(values)}
    return result


def problems(run, allowed_codes):
    """Correctness gates for one run; timing is reported, never gated."""
    found = []
    acceptance, outcomes = run["acceptance"], run["outcomes"]
    rejected = acceptance["requested"] - acceptance["accepted"]
    if rejected:
        found.append(f"{rejected} submission(s) not accepted: {acceptance['status_codes']}")
    if run["drain"]["non_terminal"]:
        found.append(f"{run['drain']['non_terminal']} accepted submission(s) did not reach a terminal state")
    unexpected = {code: count for code, count in outcomes["failure_codes"].items() if code not in allowed_codes}
    if unexpected:
        found.append(f"unexpected failure codes: {unexpected}")
    if run["executions"]:
        bad = {status: count for status, count in run["executions"]["status_codes"].items()
               if not status.isdigit() or int(status) not in EXPECTED_EXECUTION_STATUSES}
        if bad:
            found.append(f"unexpected deliberate execution statuses: {bad}")
    return found


# ---------------------------------------------------------------- host sampling
def process_tree_rss_kb(pid):
    """Resident memory of ``pid`` and its descendants, from /proc (Linux)."""
    total, pending, seen = 0, [pid], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            for line in Path(f"/proc/{current}/status").read_text(encoding="utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
            for task in Path(f"/proc/{current}/task").iterdir():
                pending.extend(int(child) for child in (task / "children").read_text(encoding="ascii").split())
        except (OSError, ValueError):
            if current == pid:
                return None
    return total


class Sampler:  # pylint: disable=too-many-instance-attributes
    """Background sampling of labelled sandbox containers and API resident memory."""

    def __init__(self, docker_client, labels, api_pid, interval):
        self.docker, self.labels, self.api_pid, self.interval = docker_client, labels, api_pid, interval
        self.peak_sandboxes = None
        self.rss = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="capacity-sampler", daemon=True)

    def sandboxes(self):
        """Current count of containers matching the label filter, or None without Docker."""
        if self.docker is None:
            return None
        return len(self.docker.containers.list(all=True, sparse=True, filters={"label": self.labels}))

    def sample(self):
        """Record one observation of sandboxes and API memory."""
        count = self.sandboxes()
        if count is not None:
            self.peak_sandboxes = max(count, self.peak_sandboxes or 0)
        if self.api_pid is not None:
            rss = process_tree_rss_kb(self.api_pid)
            if rss is not None:
                self.rss.append(rss)

    def _loop(self):
        while not self._stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.sample()
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        self.sample()


def hardware(docker_client):
    """Client host and Docker daemon facts; capacity numbers mean nothing without them."""
    info = {"platform": platform.platform(), "machine": platform.machine(),
            "python": platform.python_version(), "logical_cpus": os.cpu_count()}
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        info["cpu_model"] = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
                                  if line.startswith("model name")), None)
        meminfo = Path("/proc/meminfo").read_text(encoding="ascii").split()
        info["memory_gib"] = round(int(meminfo[meminfo.index("MemTotal:") + 1]) / 1024 ** 2, 1)
    except (OSError, ValueError):
        pass
    if docker_client is not None:
        daemon = docker_client.info()
        info["docker"] = {"server_version": daemon.get("ServerVersion"), "cpus": daemon.get("NCPU"),
                          "memory_gib": round(daemon.get("MemTotal", 0) / 1024 ** 3, 1),
                          "default_runtime": daemon.get("DefaultRuntime"),
                          "runtimes": sorted(daemon.get("Runtimes") or {})}
    return info


def connect_docker(enabled):
    """A Docker client for sampling, or None with the reason it is unavailable."""
    if not enabled:
        return None, "disabled with --no-docker"
    try:
        import docker  # pylint: disable=import-outside-toplevel  # optional: --no-docker works without it
        client = docker.from_env()
        client.ping()
        return client, None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return None, f"Docker unavailable: {type(exc).__name__}"


# ---------------------------------------------------------------- HTTP
async def ensure_config(client, alias, definition):
    """Create the alias once; afterwards update it in place and reactivate it."""
    current = await client.get(f"{API}/configs/{alias}")
    if current.status_code == 404:
        response = await client.post(f"{API}/configs", json={"external_assignment_id": alias,
                                                             "definition": definition})
    elif current.status_code == 200:
        response = await client.patch(f"{API}/configs/external/{alias}",
                                      headers={"If-Match": current.headers["ETag"]},
                                      json={"definition": definition, "is_active": True})
    else:
        response = current
    if response.status_code != 200:
        raise SetupError(f"configuration {alias}: HTTP {response.status_code} {response.text[:500]}")
    return response.json()["id"]


async def deactivate_config(client, alias):
    """Leave nothing active behind; a missing alias was never created by this run."""
    current = await client.get(f"{API}/configs/{alias}")
    if current.status_code != 200 or not current.json()["is_active"]:
        return
    await client.patch(f"{API}/configs/external/{alias}", headers={"If-Match": current.headers["ETag"]},
                       json={"is_active": False})


async def _timed(request):
    started = time.perf_counter()
    try:
        response = await request
        return str(response.status_code), time.perf_counter() - started, response
    except httpx.HTTPError as exc:
        return type(exc).__name__, time.perf_counter() - started, None


async def wait_terminal(client, user_id, accepted_ids, deadline, interval):
    """Poll the run's compact history (two requests per 200 rows) until all are terminal."""
    rows = {}
    while True:
        rows, offset = {}, 0
        while True:
            page = await client.get(f"{API}/submissions", params={"external_user_id": user_id,
                                                                   "limit": 100, "offset": offset})
            page.raise_for_status()
            batch = page.json()
            rows.update((row["id"], row) for row in batch if row["id"] in accepted_ids)
            if len(batch) < 100:
                break
            offset += 100
        if all(rows.get(sid, {}).get("status") in TERMINAL for sid in accepted_ids):
            return rows
        if time.monotonic() >= deadline:
            return rows
        await asyncio.sleep(interval)


async def fetch_details(client, ids, concurrency=8):
    """Authenticated details carry outcome timestamps; fetched after the drain, bounded."""
    gate = asyncio.Semaphore(concurrency)

    async def one(sid):
        async with gate:
            response = await client.get(f"{API}/submissions/{sid}/details")
            response.raise_for_status()
            return response.json()
    return await asyncio.gather(*(one(sid) for sid in ids))


async def settle_sandboxes(sampler, baseline, deadline, interval):
    """Disposal is asynchronous; wait (bounded) for the labelled count to return to baseline."""
    count = sampler.sandboxes()
    while count is not None and count > baseline and time.monotonic() < deadline:
        await asyncio.sleep(interval)
        count = sampler.sandboxes()
    return count


async def run_once(client, args, number, submissions, docker_client, docker_error):  # pylint: disable=too-many-arguments,too-many-locals
    """One burst: submit, wait for terminal states, then measure."""
    run_id = uuid.uuid4().hex[:12]
    user_id = f"capacity-benchmark-{run_id}"
    payloads = [{"external_assignment_id": alias, "external_user_id": user_id, "username": "Capacity Benchmark",
                 "files": files} for alias, files in submissions(run_id)]
    executions = [execution_request(f"{run_id}-exec-{index}") for index in range(args.executions)]
    load_start = os.getloadavg()
    sampler = Sampler(docker_client, args.sandbox_label, args.api_pid, args.sample_interval)
    started_at = datetime.now(timezone.utc)
    with sampler:
        baseline = sampler.peak_sandboxes
        burst_start = time.perf_counter()
        results = await asyncio.gather(
            *(_timed(client.post(f"{API}/submissions", json=payload)) for payload in payloads),
            *(_timed(client.post(f"{API}/execute", json=payload)) for payload in executions))
        burst_seconds = time.perf_counter() - burst_start
        posted, executed = results[:len(payloads)], results[len(payloads):]
        accepted = {response.json()["id"] for status, _, response in posted if status == "202"}
        rows = await wait_terminal(client, user_id, accepted, time.monotonic() + args.timeout, args.poll_interval)
    terminal = [row for row in rows.values() if row["status"] in TERMINAL]
    details = await fetch_details(client, [row["id"] for row in terminal])
    after = None
    if docker_client is not None:
        after = await settle_sandboxes(sampler, baseline, time.monotonic() + args.settle_timeout,
                                       args.poll_interval)

    submitted = [_timestamp(row["submitted_at"]) for row in rows.values()]
    graded = [_timestamp(row["graded_at"]) for row in terminal if row["graded_at"]]
    drain = (max(graded) - min(submitted)).total_seconds() if graded and submitted else None
    queue_wait, durations = [], []
    for detail in details:
        outcome = detail.get("outcome")
        if outcome:
            queue_wait.append((_timestamp(outcome["started_at"]) - _timestamp(detail["submitted_at"])).total_seconds())
            durations.append(outcome["duration_ms"] / 1000)
    failed = [row for row in terminal if row["status"] == "failed"]
    run = {
        "run": number,
        "run_id": run_id,
        "external_user_id": user_id,
        "started_at": started_at.isoformat(),
        "acceptance": {
            "requested": len(payloads),
            "accepted": len(accepted),
            "status_codes": dict(Counter(status for status, _, _ in posted)),
            "latency_seconds": percentiles([latency for _, latency, _ in posted]),
            "burst_seconds": round(burst_seconds, 3),
        },
        "drain": {
            "seconds": round(drain, 3) if drain is not None else None,
            # Completed gradings only: a fast capacity failure is not throughput.
            "gradings_per_minute": round((len(terminal) - len(failed)) / drain * 60, 1) if drain else None,
            "terminal": len(terminal),
            "non_terminal": len(accepted) - len(terminal),
        },
        "outcomes": {
            "completed": len(terminal) - len(failed),
            "failed": len(failed),
            "failure_codes": dict(Counter((row.get("error") or {}).get("code", "UNKNOWN") for row in failed)),
            "scores": {str(score): count for score, count in sorted(Counter(
                row["final_score"] for row in terminal if row["status"] == "completed").items())},
        },
        "queue_wait_seconds": percentiles(queue_wait),
        "grading_duration_seconds": percentiles(durations),
        "executions": {
            "requested": len(executions),
            "status_codes": dict(Counter(status for status, _, _ in executed)),
            "latency_seconds": percentiles([latency for _, latency, _ in executed]),
        } if executions else None,
        "sandboxes": ({"label_filter": args.sandbox_label, "before": baseline, "peak": sampler.peak_sandboxes,
                       "after": after, "leftover": max(0, after - baseline)}
                      if docker_client is not None else {"unavailable": docker_error}),
        "api_rss_mb": ({"start": round(sampler.rss[0] / 1024, 1), "peak": round(max(sampler.rss) / 1024, 1),
                        "end": round(sampler.rss[-1] / 1024, 1)} if sampler.rss else None),
        "load_average": {"start": [round(value, 2) for value in load_start],
                         "end": [round(value, 2) for value in os.getloadavg()]},
    }
    run["problems"] = problems(run, set(args.allow_failure))
    return run


async def benchmark(args):
    """Set up the configurations, run every burst and always deactivate them."""
    docker_client, docker_error = connect_docker(not args.no_docker)
    headers = {"Authorization": f"Bearer {args.token}"}
    limits = httpx.Limits(max_connections=args.submissions + args.executions + 8)
    timeout = httpx.Timeout(args.request_timeout)
    definitions, submissions = plan(args)
    async with httpx.AsyncClient(base_url=args.url.rstrip("/"), headers=headers, limits=limits,
                                 timeout=timeout) as client:
        ready = await client.get(f"{API}/ready")
        if ready.status_code != 200:
            raise SetupError(f"stack not ready: HTTP {ready.status_code} {ready.text[:500]}")
        health = (await client.get(f"{API}/health")).json()
        try:
            for alias, definition in definitions.items():
                await ensure_config(client, alias, definition)
            runs = [await run_once(client, args, number, submissions, docker_client, docker_error)
                    for number in range(1, args.runs + 1)]
        finally:
            for alias in definitions:
                await deactivate_config(client, alias)
    report = {
        "benchmark": {"workload": args.workload, "submissions": args.submissions, "runs": args.runs,
                      "python_io_tests": args.tests if args.workload != "webdev" else None,
                      "webdev_criteria": args.criteria if args.workload != "python-io" else None,
                      "webdev_page_kb": args.page_kb if args.workload != "python-io" else None,
                      "executions": args.executions, "allowed_failure_codes": sorted(args.allow_failure),
                      "url": args.url, "configurations": sorted(definitions)},
        "environment": {"client": hardware(docker_client), "stack_version": health.get("version")},
        "runs": runs,
        "variance": variance(runs) if len(runs) > 1 else None,
    }
    report["problems"] = [f"run {run['run']}: {problem}" for run in runs for problem in run["problems"]]
    report["passed"] = not report["problems"]
    if docker_client is not None:
        docker_client.close()
    return report


def summary(report):
    """Human-readable lines for stderr; the JSON report is authoritative."""
    lines = []
    for run in report["runs"]:
        acceptance, drain, outcomes = run["acceptance"], run["drain"], run["outcomes"]
        latency = acceptance["latency_seconds"] or {}
        line = (f"run {run['run']} {report['benchmark']['workload']}: "
                f"{acceptance['accepted']}/{acceptance['requested']} accepted {acceptance['status_codes']}, "
                f"acceptance p50 {latency.get('p50')}s p95 {latency.get('p95')}s; "
                f"{drain['terminal']} terminal in {drain['seconds']}s ({drain['gradings_per_minute']}/min); "
                f"completed {outcomes['completed']}, failed {outcomes['failed']} {outcomes['failure_codes'] or ''}")
        if run["queue_wait_seconds"]:
            line += f"; queue wait p95 {run['queue_wait_seconds']['p95']}s"
        if run["grading_duration_seconds"]:
            line += f"; grading p50 {run['grading_duration_seconds']['p50']}s"
        if run["executions"]:
            line += f"; executions {run['executions']['status_codes']}"
        sandboxes = run["sandboxes"]
        if "peak" in sandboxes:
            line += f"; sandboxes peak {sandboxes['peak']} leftover {sandboxes['leftover']}"
        if run["api_rss_mb"]:
            line += f"; API RSS peak {run['api_rss_mb']['peak']} MB"
        lines.append(line)
    lines.append("PASS" if report["passed"] else "FAIL: " + "; ".join(report["problems"]))
    return "\n".join(lines)


def parse_args(argv=None):
    """Command-line options; defaults are the JOBS.md reference workloads."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000", help="API root (default %(default)s)")
    parser.add_argument("--token", default=os.getenv("AUTOGRADER_INTEGRATION_TOKEN"),
                        help="integration token (default: $AUTOGRADER_INTEGRATION_TOKEN)")
    parser.add_argument("--workload", choices=WORKLOADS, default="python-io")
    parser.add_argument("--submissions", type=int, default=200, help="burst size (default %(default)s)")
    parser.add_argument("--tests", type=int, default=5, help="python-io stdin/stdout tests (default %(default)s)")
    parser.add_argument("--criteria", type=int, default=30, help="webdev has_tag criteria (default %(default)s)")
    parser.add_argument("--page-kb", type=int, default=20, help="webdev page size (default %(default)s)")
    parser.add_argument("--executions", type=int, default=None,
                        help="concurrent POST /execute calls (default 12 for mix, else 0)")
    parser.add_argument("--allow-failure", action="append", default=[], metavar="CODE",
                        help="failure code that does not fail the benchmark (repeatable)")
    parser.add_argument("--runs", type=int, default=1, help="repeat the burst; reports min/median/max")
    parser.add_argument("--timeout", type=float, default=1800,
                        help="seconds after a burst for every submission to terminate (default %(default)s)")
    parser.add_argument("--request-timeout", type=float, default=120, help="per HTTP request (default %(default)s)")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="history polling (default %(default)s)")
    parser.add_argument("--sample-interval", type=float, default=0.5,
                        help="sandbox/RSS sampling (default %(default)s)")
    parser.add_argument("--settle-timeout", type=float, default=30,
                        help="bound on waiting for sandbox disposal after a run (default %(default)s)")
    parser.add_argument("--api-pid", type=int, help="API process id on this host, for RSS (with children)")
    parser.add_argument("--sandbox-label", action="append", metavar="KEY=VALUE",
                        help=f"Docker label selecting this stack's sandboxes (repeatable; default {SANDBOX_APP_LABEL})")
    parser.add_argument("--no-docker", action="store_true", help="skip sandbox sampling (remote Docker host)")
    args = parser.parse_args(argv)
    if args.executions is None:
        args.executions = 12 if args.workload == "mix" else 0
    args.sandbox_label = args.sandbox_label or [SANDBOX_APP_LABEL]
    if not args.token:
        parser.error("an integration token is required (--token or AUTOGRADER_INTEGRATION_TOKEN)")
    if min(args.submissions, args.tests, args.criteria, args.page_kb, args.runs) < 1 or args.executions < 0:
        parser.error("sizes and run counts must be positive")
    return args


def main(argv=None):
    """Run the benchmark; returns the process exit status (0 pass, 1 fail, 2 setup)."""
    args = parse_args(argv)
    try:
        report = asyncio.run(benchmark(args))
    except SetupError as exc:
        print(f"capacity benchmark setup failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    print(summary(report), file=sys.stderr)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
