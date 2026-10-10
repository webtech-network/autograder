"""Grade one checkout, retain its outcome, then optionally publish it."""
import argparse
import json
import logging
import os
from pathlib import Path
import stat

from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.contracts.definition import DefinitionValidationError
from autograder.models.contracts.outcome import validate_outcome
from github_action.cloud_client import CloudClient, CloudClientError, CloudConnectionError
from github_action.github_action_service import GithubActionService
from submission_contract import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_FILE_BYTES,
    validate_content,
    validate_filename,
)

logger = logging.getLogger(__name__)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--execution-mode", choices=("repo", "external"), default="repo")
parser.add_argument("--definition-path", default=".github/autograder/definition.json")
parser.add_argument("--submission-root", default=".")
parser.add_argument("--student-name", default=os.getenv("GITHUB_ACTOR", "local"))
parser.add_argument("--submission-language")
parser.add_argument("--locale", choices=("en", "pt-br"), default="en")
parser.add_argument("--grading-config-id", type=int)
parser.add_argument("--autograder-cloud-url")
parser.add_argument("--autograder-cloud-token")
parser.add_argument("--upload-to-cloud", choices=("true", "false"), default="false")
parser.add_argument("--retry-delivery-path")


def workspace_path(value):
    path = Path(value)
    return path if path.is_absolute() else Path(os.getenv("GITHUB_WORKSPACE", ".")) / path


def collect_files(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("submission-root must be an existing readable directory.")
    files = {}
    total_bytes = 0

    def walk_error(error):
        raise ValueError("submission-root contains an unreadable directory.") from error

    for directory, directories, filenames in os.walk(root, onerror=walk_error):
        directories[:] = sorted(d for d in directories if d not in (".git", ".github", ".autograder"))
        for name in directories:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Submission directories must not be symbolic links.")
        for name in sorted(filenames):
            path = Path(directory) / name
            filename = validate_filename(path.relative_to(root).as_posix())
            if len(files) >= MAX_FILES:
                raise ValueError(f"Submission must contain at most {MAX_FILES} files.")
            try:
                if not stat.S_ISREG(path.lstat().st_mode):
                    raise ValueError(f"Submission files must be regular files: {filename}")
                # Binary reading preserves CRLF and bounds memory before decoding.
                limit = min(MAX_FILE_BYTES, MAX_TOTAL_FILE_BYTES - total_bytes)
                with path.open("rb") as handle:
                    data = handle.read(limit + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError(f"Submission file exceeds {MAX_FILE_BYTES} bytes: {filename}")
                if total_bytes + len(data) > MAX_TOTAL_FILE_BYTES:
                    raise ValueError(f"Submission exceeds {MAX_TOTAL_FILE_BYTES} total file bytes.")
                content = validate_content(data.decode("utf-8"))
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"Submission file is not readable UTF-8 text: {filename}") from exc
            files[filename] = SubmissionFile(filename=filename, content=content)
            total_bytes += len(data)
    if not files:
        raise ValueError("submission-root contains no submission files.")
    return files


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def output(key, value):
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")


def retain_outcome(value):
    value = validate_outcome(value).model_dump(mode="json")
    result_path = workspace_path(".autograder/outcome.json")
    write_json(result_path, value)
    output("status", value["status"])
    if value.get("score") is not None:
        output("score", value["score"])
    output("result-path", ".autograder/outcome.json")
    feedback = value.get("feedback", {})
    if isinstance(feedback, dict) and feedback.get("content"):
        result_path.with_name("feedback.md").write_text(feedback["content"], encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write("## Autograder\n\n")
            handle.write(f"Status: {value['status']}\n\n")
            if value.get("score") is not None:
                handle.write(f"Score: {value['score']}/100\n\n")
            handle.write("Canonical outcome: `.autograder/outcome.json`.\n")
    return result_path


def run(args):
    wants_delivery = args.upload_to_cloud == "true" or bool(args.retry_delivery_path)
    if args.execution_mode == "external" or wants_delivery:
        if not args.autograder_cloud_url or not args.autograder_cloud_token:
            raise ValueError("Cloud URL and token are required for cloud configuration or publication.")
        if not args.retry_delivery_path and (args.grading_config_id is None or args.grading_config_id <= 0):
            raise ValueError("A positive grading-config-id is required for cloud configuration or publication.")
    if args.retry_delivery_path:
        payload = json.loads(workspace_path(args.retry_delivery_path).read_text(encoding="utf-8"))
        # The server validates the saved attestation. Do not rerun evaluation.
        retain_outcome(payload["outcome"])
        client = CloudClient(args.autograder_cloud_url, args.autograder_cloud_token)
        try:
            response = client.submit_external_result(payload)
        except Exception as exc:
            raise RuntimeError("Result delivery failed; the grading artifact is retained.") from exc
        if response.get("submission_id") is not None:
            output("submission-id", response["submission_id"])
        return payload["outcome"]["status"] == "completed"
    service = GithubActionService()
    pipeline = service.configure(
        definition_path=workspace_path(args.definition_path), execution_mode=args.execution_mode,
        grading_config_id=args.grading_config_id, cloud_url=args.autograder_cloud_url,
        cloud_token=args.autograder_cloud_token, upload_to_cloud=wants_delivery,
        language=args.submission_language, locale=args.locale,
    )
    outcome = service.run_autograder(pipeline, args.student_name, collect_files(workspace_path(args.submission_root)))
    value = outcome.model_dump(mode="json")
    result_path = retain_outcome(value)
    if value["status"] == "failed":
        logger.error("Grading failed: %s (%s)", value["error"]["message"], value["error"]["code"])
    payload = service.delivery_payload(outcome, args.student_name)
    if payload is not None:
        write_json(result_path.with_name("delivery.json"), payload)
        try:
            response = service.publish(payload)
        except Exception as exc:
            raise RuntimeError("Result delivery failed; the grading artifact and delivery.json are retained.") from exc
        if response.get("submission_id") is not None:
            output("submission-id", response["submission_id"])
    return value["status"] == "completed"


def main(argv=None):
    args = parser.parse_args(argv)
    try:
        if not run(args):
            raise SystemExit(1)
    except DefinitionValidationError as exc:
        logger.error("Invalid grading definition: %s", json.dumps(exc.errors(), ensure_ascii=False))
        raise SystemExit(1) from exc
    except (ValueError, OSError, RuntimeError, KeyError, CloudClientError, CloudConnectionError) as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
