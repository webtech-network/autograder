"""Submission identity, run provenance and publication trust for the Action (INT-02).

Three identities are deliberately separate:

* the **submitter** owns the graded work (an opaque ID chosen by Prisma/the
  workflow, or the repository for ordinary one-repository-per-student grading);
* the **actor** merely started or re-ran the workflow;
* the **producer** is the authenticated credential that publishes the attestation.

Credentials never enter any of them. See docs/github_action/trust.md.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess

# Events whose workflow and secrets are controlled by the repository's writers.
PUBLISHING_EVENTS = frozenset({"push", "workflow_dispatch", "repository_dispatch", "schedule", "pull_request"})
# Events that run with secrets on behalf of code the repository does not control.
UNSAFE_EVENTS = {
    "pull_request_target": "runs with repository secrets for pull requests from forks",
    "workflow_run": "publishes with secrets after a workflow that may have run untrusted code",
}
EXCLUDED_DIRECTORIES = (".git", ".github", ".autograder")
_OPAQUE_ID = re.compile(r"[\x21-\x7e]{1,255}")


class TrustError(ValueError):
    """An unsupported event/runner combination for authoritative publication."""


@dataclass(frozen=True)
class SubmissionIdentity:
    submitter_id: str
    submitter_name: str
    source: str  # "input" | "repository" | "local"


@dataclass(frozen=True)
class RunProvenance:
    repository: str | None
    repository_id: str | None
    event_name: str | None
    ref: str | None
    event_sha: str | None
    evaluated_commit: str | None
    evaluated_tree_matches_commit: bool | None
    run_id: str | None
    run_attempt: str | None
    workflow_ref: str | None
    actor: str | None
    triggering_actor: str | None
    runner_environment: str | None

    def metadata(self) -> dict:
        return asdict(self)


def resolve_identity(submitter_id: str | None, submitter_name: str | None, env=os.environ) -> SubmissionIdentity:
    """Authoritative opaque identity; never derived from the triggering actor."""
    submitter_id = (submitter_id or "").strip() or None
    submitter_name = (submitter_name or "").strip() or None
    if submitter_id is not None:
        if not _OPAQUE_ID.fullmatch(submitter_id):
            raise ValueError("submitter-id must be 1-255 visible ASCII characters.")
        return SubmissionIdentity(submitter_id, (submitter_name or submitter_id)[:255], "input")
    repository_id = env.get("GITHUB_REPOSITORY_ID")
    if repository_id:
        # One repository per student (e.g. GitHub Classroom): the repository owns the work.
        return SubmissionIdentity(f"github-repository:{repository_id}",
                                  (submitter_name or env.get("GITHUB_REPOSITORY") or repository_id)[:255],
                                  "repository")
    return SubmissionIdentity("local", (submitter_name or "local")[:255], "local")


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(root), *args],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def evaluated_commit(root: Path) -> tuple[str | None, bool | None]:
    """The commit checked out in `root`, and whether the graded files equal it.

    Untracked, modified and ignored files under the submission root are graded
    too, so any of them means the files are not exactly that commit.
    """
    head = _git(root, "rev-parse", "--verify", "HEAD")
    if head is None:
        return None, None
    # Mirror collect_files: .git, .github and .autograder are never graded.
    excluded = [f":(exclude,glob)**/{name}/**" for name in EXCLUDED_DIRECTORIES]
    status = _git(root, "status", "--porcelain", "--untracked-files=all", "--ignored", "--", ".", *excluded)
    return head.strip(), (status == "" if status is not None else None)


def run_provenance(submission_root: Path, env=os.environ) -> RunProvenance:
    commit, matches = evaluated_commit(submission_root)
    return RunProvenance(
        repository=env.get("GITHUB_REPOSITORY"), repository_id=env.get("GITHUB_REPOSITORY_ID"),
        event_name=env.get("GITHUB_EVENT_NAME"), ref=env.get("GITHUB_REF"), event_sha=env.get("GITHUB_SHA"),
        evaluated_commit=commit, evaluated_tree_matches_commit=matches,
        run_id=env.get("GITHUB_RUN_ID"), run_attempt=env.get("GITHUB_RUN_ATTEMPT"),
        workflow_ref=env.get("GITHUB_WORKFLOW_REF"), actor=env.get("GITHUB_ACTOR"),
        triggering_actor=env.get("GITHUB_TRIGGERING_ACTOR"), runner_environment=env.get("RUNNER_ENVIRONMENT"),
    )


def _is_fork_pull_request(env) -> bool | None:
    path = env.get("GITHUB_EVENT_PATH")
    if not path:
        return None
    try:
        event = json.loads(Path(path).read_text(encoding="utf-8"))
        head = event["pull_request"]["head"]["repo"]
        base = event["pull_request"]["base"]["repo"]
        return head is None or head.get("full_name") != base.get("full_name")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def check_publication_trust(env=os.environ, *, trusted_self_hosted_runner: bool = False) -> None:
    """Refuse publication from event/runner combinations listed as unsupported."""
    if env.get("GITHUB_ACTIONS") != "true":
        return  # an operator's local/CI shell; the credential holder is trusted
    event = env.get("GITHUB_EVENT_NAME", "")
    if event in UNSAFE_EVENTS:
        raise TrustError(f"Cloud publication is not supported for '{event}' events: it {UNSAFE_EVENTS[event]}. "
                         "Use server-side grading (POST /api/v1/submissions) through a trusted broker instead.")
    if event not in PUBLISHING_EVENTS:
        raise TrustError(f"Cloud publication is not supported for '{event or 'unknown'}' events. "
                         f"Supported events: {', '.join(sorted(PUBLISHING_EVENTS))}.")
    if event == "pull_request":
        fork = _is_fork_pull_request(env)
        if fork is not False:
            raise TrustError("Cloud publication from a pull request requires a same-repository pull request; "
                             "fork pull requests (or an unreadable event payload) cannot publish.")
    if env.get("RUNNER_ENVIRONMENT") != "github-hosted" and not trusted_self_hosted_runner:
        raise TrustError("Cloud publication from a self-hosted (or unidentified) runner requires "
                         "trusted-self-hosted-runner: \"true\" after reviewing docs/github_action/trust.md.")
