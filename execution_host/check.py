"""Check a grading definition, then optionally grade reference submissions with it.

    python -m execution_host.check DEFINITION [--submission DIR]... [--language L] [--locale L] [--min-score N]

The definition is compiled exactly as the HTTP service and the Action compile
it: every error is printed with its JSON path. Each ``--submission`` directory
is then read as the Action reads a checkout and graded through the same
pipeline, on this machine's Docker for code-running criteria (the Action's
``RunnerHost``: one sandbox at a time, created on demand, removed afterwards).

Exit status: 0 the definition is valid and every reference completed (at or
above ``--min-score``); 1 the definition is invalid, or a reference failed to
grade or scored below ``--min-score``; 2 the check could not run (usage,
unreadable input, or no Docker, runtime image or provider for grading).
"""
import argparse
import json
import logging
import sys
import threading
from pathlib import Path

from autograder import CompiledDefinition, DefinitionValidationError, Submission, compile_definition
from autograder import evaluate_submission, select_language
from autograder.models.capabilities import budget_problems, requirements_for
from autograder.models.contracts.outcome import TerminalOutcome
from autograder.models.locale import DEFAULT_LOCALE, LOCALE_IDS, parse_locale
from execution_host.runner import DockerUnavailableError, RunnerHost, provider_capabilities
from execution_host.submission_files import collect_files
from sandbox_manager.errors import IsolationRuntimeError, RuntimeImageError, RuntimeUnavailableError
from sandbox_manager.models.pool_config import SandboxHostConfig

VALID, PROBLEM, UNAVAILABLE = 0, 1, 2
#: Failure categories that are about this machine, not about the definition or the reference.
UNAVAILABLE_CATEGORIES = {"capability", "provider", "internal"}


class CheckUnavailable(Exception):
    """The check cannot run here; the message says why and what to do."""


def score(value: str) -> float:
    """A ``--min-score`` value: a number of points from 0 to 100."""
    number = float(value)
    if not 0 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return number


parser = argparse.ArgumentParser(prog="python -m execution_host.check", description=__doc__.split("\n\n", maxsplit=1)[0])
parser.add_argument("definition", type=Path, help="Grading definition JSON file")
parser.add_argument("--submission", type=Path, action="append", default=[], metavar="DIR",
                    help="Reference submission directory to grade; repeat for several")
parser.add_argument("--language", help="Language of the submissions; required when the definition allows several")
parser.add_argument("--locale", type=parse_locale, default=DEFAULT_LOCALE,
                    metavar="{" + ",".join(LOCALE_IDS) + "}", help="Feedback locale")
parser.add_argument("--min-score", type=score, metavar="N", help="Fail a reference that completes below N")
parser.add_argument("--verbose", action="store_true", help="Show the engine's and the sandbox host's logs")


class BriefFormatter(logging.Formatter):
    """One line per record, without tracebacks: the outcome already explains a failed grading."""

    def format(self, record):
        return f"{record.levelname.lower()}: {record.getMessage()}"


def configure_logging(verbose: bool) -> None:
    """Logs go to stderr; without ``--verbose`` only infrastructure warnings, one line each."""
    handler = logging.StreamHandler(sys.stderr)
    if verbose:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
        return
    handler.setFormatter(BriefFormatter())
    logging.basicConfig(level=logging.WARNING, handlers=[handler])
    # Every engine failure is in the printed outcome; infrastructure warnings (for
    # example a sandbox that could not be removed) still reach stderr.
    logging.getLogger("autograder").setLevel(logging.CRITICAL)


def json_path(path) -> str:
    """``criteria.base.tests[0].type`` for ``["criteria", "base", "tests", 0, "type"]``."""
    text = ""
    for part in path:
        text += f"[{part}]" if isinstance(part, int) else (f".{part}" if text else str(part))
    return text or "(definition)"


def print_errors(errors) -> None:
    """One line per error: its JSON path, message and code."""
    for error in errors:
        print(f"  {json_path(error['path'])}: {error['message']} [{error['code']}]")


def load_definition(path: Path):
    """The parsed JSON, or None after printing why it is not JSON."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CheckUnavailable(f"Cannot read {path}: {getattr(exc, 'strerror', None) or exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"{path}:{exc.lineno}:{exc.colno}: not valid JSON: {exc.msg}")
        return None


def host_maximum() -> float | None:
    """The longest sandbox this machine's ``sandbox_config.yml`` grants, if the file is present."""
    try:
        return SandboxHostConfig.load_from_yaml().running_timeout
    except FileNotFoundError:
        return None


def validate(path: Path) -> CompiledDefinition | None:
    """Compile and report; None when the definition has problems (already printed)."""
    value = load_definition(path)
    if value is None:
        return None
    try:
        compiled = compile_definition(value)
    except DefinitionValidationError as exc:
        print(f"{path} is invalid:")
        print_errors(exc.errors())
        return None
    maximum = host_maximum()
    problems = budget_problems(compiled, compiled.definition.languages, maximum)
    if problems:
        print(f"{path} is invalid on this host:")
        print_errors(problems)
        return None
    print(f"{path} is valid (definition hash {compiled.definition_hash[:12]}).")
    granted = f"; this host grants {maximum:g} s" if maximum is not None else ""
    for language in compiled.definition.languages:
        requirements = requirements_for(compiled, select_language(compiled, language))
        if "sandbox_execution" not in requirements.capabilities:
            print(f"  {language}: no sandbox (nothing runs the submission)")
            continue
        processes = requirements.budget.processes
        print(f"  {language}: {processes} process{'' if processes == 1 else 'es'}, sandbox lifetime up to "
              f"{requirements.budget.session_seconds:g} s{granted}")
    return compiled


def print_group(node, depth) -> None:
    """Scores in one column, the tree indented after it: criteria as ``ID  name`` with their report."""
    indent = "  " * depth
    for test in node.get("tests") or []:
        print(f"  {test['score']:6.2f}  {indent}{test['id']}  {test['name']}")
        for line in (test.get("report") or "").splitlines():
            print(f"          {indent}  {line}")
    for subject in node.get("subjects") or []:
        print(f"  {subject['score']:6.2f}  {indent}{subject['name']}")
        print_group(subject, depth + 1)


def report(directory: Path, outcome: dict, min_score: float | None) -> int:
    """Print one reference's outcome; its exit status."""
    print(f"\nReference {directory} ({outcome['language']}): ", end="")
    if outcome["status"] == "failed":
        error = outcome["error"]
        print(f"failed: {error['code']}: {error['message']}")
        if error.get("output"):
            print("\n".join(f"    {line}" for line in error["output"].splitlines()))
        return UNAVAILABLE if error["category"] in UNAVAILABLE_CATEGORIES else PROBLEM
    print(f"completed, score {outcome['score']:.2f}/100")
    for name in ("base", "bonus", "penalty"):
        category = outcome["tree"].get(name)
        if category is not None:
            print(f"  {category['score']:6.2f}  {name} (weight {category['weight']:g})")
            print_group(category, 1)
    feedback = outcome["feedback"]
    if feedback["status"] == "completed":
        print("Feedback:\n" + feedback["content"])
    else:
        print(f"Feedback: {feedback['status']}" + (f" ({feedback['error']['code']})" if feedback.get("error") else ""))
    if min_score is not None and outcome["score"] < min_score:
        print(f"Reference {directory} scored {outcome['score']:.2f}, below --min-score {min_score:g}.")
        return PROBLEM
    return VALID


def open_capabilities(compiled, language):
    """The Action's host for ``language``: Docker only when the definition runs code in it."""
    if "sandbox_execution" not in requirements_for(compiled, language).capabilities:
        return None, provider_capabilities()
    try:
        host = RunnerHost(language)
    except DockerUnavailableError as exc:
        raise CheckUnavailable(
            f"Docker is not reachable, and this definition runs {language.value} code, which the check grades in a "
            "local Docker sandbox. Start Docker (or set DOCKER_HOST), or omit --submission to only validate."
        ) from exc
    except (RuntimeUnavailableError, RuntimeImageError, IsolationRuntimeError) as exc:
        raise CheckUnavailable(f"The {language.value} runtime is unavailable: {exc}") from exc
    return host, host.capabilities


def grade(compiled, submission, capabilities) -> TerminalOutcome:
    """Grade in a worker so Ctrl-C interrupts only this wait, never the sandbox bookkeeping;
    the caller's ``finally`` then removes the sandbox (as the Action does on SIGTERM)."""
    result = {}

    def run():
        try:
            result["outcome"] = evaluate_submission(submission, definition=compiled, capabilities=capabilities)
        except BaseException as exc:  # pylint: disable=broad-exception-caught  # re-raised below
            result["error"] = exc

    worker = threading.Thread(target=run, name="grading", daemon=True)
    worker.start()
    worker.join()
    if "error" in result:
        raise result["error"]
    return result["outcome"]


def check(args) -> int:
    """Validate, then grade each reference; the exit status."""
    compiled = validate(args.definition)
    if compiled is None:
        return PROBLEM
    if not args.submission:
        return VALID
    try:
        language = select_language(compiled, args.language)
    except DefinitionValidationError as exc:
        [error] = exc.errors()
        raise CheckUnavailable(f"--language: {error['message']}") from exc
    submissions = []
    for directory in args.submission:
        try:
            submissions.append((directory, collect_files(directory)))
        except ValueError as exc:
            raise CheckUnavailable(str(exc)) from exc
    host, capabilities = open_capabilities(compiled, language)
    status = VALID
    try:
        for directory, files in submissions:
            submission = Submission(username=str(directory), user_id="reference", assignment_id="check",
                                    submission_files=files, language=language, locale=args.locale)
            outcome = grade(compiled, submission, capabilities).model_dump(mode="json")
            status = max(status, report(directory, outcome, args.min_score))
    finally:
        if host is not None:
            host.close()
    return status


def main(argv=None) -> int:
    """The command line entry point; returns the exit status."""
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    try:
        return check(args)
    except CheckUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return UNAVAILABLE


if __name__ == "__main__":
    sys.exit(main())
