"""
GitHub Action Adapter for Autograder.

This module provides the entry point for the GitHub Action adapter that integrates
with the autograder workflow to process student submissions and generate feedback.
"""

import logging
import os
from argparse import ArgumentParser
from .github_action_service import GithubActionService
from autograder.autograder import AutograderPipeline
import asyncio

logger = logging.getLogger(__name__)

parser = ArgumentParser(description="GitHub Action Adapter for Autograder")
parser.add_argument("--github-token", type=str, required=True, help="GitHub Token")
parser.add_argument(
    "--template-preset",
    type=str,
    required=True,
    help="The grading preset to use (e.g., api, html, python, etc.)",
)
parser.add_argument(
    "--student-name", type=str, required=True, help="The name of the student"
)
parser.add_argument(
    "--feedback-type",
    type=str,
    default="default",
    help="The type of feedback to provide (default or ai)",
)
parser.add_argument(
    "--custom-template",
    type=str,
    required=False,
    help="Test Files for the submission (in case of custom preset)",
)
parser.add_argument("--app-token", type=str, required=False, help="GitHub App Token")
parser.add_argument(
    "--openai-key",
    type=str,
    required=False,
    help="OpenAI API key for AI feedback (required only for AI feedback mode)",
)
parser.add_argument(
    "--include-feedback",
    type=str,
    required=False,
    help="Whether to include/generate feedback (true/false).",
)


async def main():
    """
    This is the entry point for the GitHub Action adapter.
    This makes the Adapter accessible to the GitHub Action workflow,
    that runs by entrypoint.sh script with all arguments passed to it.
    """
    try:
        args = __parser_values()

        if args.template_preset == "custom":
            raise SystemExit("Currently, this system does not accept custom templates.")

        include_feedback = __has_feedback(args.include_feedback)

        if args.openai_key:
            os.environ["OPENAI_API_KEY"] = args.openai_key

        service = GithubActionService(args.github_token, args.app_token)
        pipeline = __build_pipeline(args, include_feedback, service)
        grading_result = __retrieve_grading_score(args, service, pipeline)

        service.export_results(
            grading_result.final_score, include_feedback, grading_result.feedback
        )
    except ValueError as e:
        logger.error("You fill a wrong value: %s", e)
    except SystemExit as e:
        logger.critical(e)
    except Exception as e:
        logger.error(e, exc_info=True)


def __retrieve_grading_score(
    args, service: GithubActionService, pipeline: AutograderPipeline
):
    grading_result = service.run_autograder(
        pipeline,
        args.student_name,
        __get_submission_files(),
    ).result
    if grading_result is None:
        raise RuntimeError("Failed to get grading result: autograder returned None")
    logger.info("Final Score for %s: %s", args.student_name, grading_result.final_score)

    return grading_result


def __get_submission_files():
    """
    Collect all files from the submission directory, skipping .git and .github.

    Returns:
        dict: A dictionary mapping relative file paths to their contents.
    """
    base_path = os.getenv("GITHUB_WORKSPACE", ".")
    submission_path = os.path.join(base_path, "submission")
    submission_files_dict = {}

    for root, dirs, files in os.walk(submission_path):
        if ".git" in dirs:
            dirs.remove(".git")
        if ".github" in dirs:
            dirs.remove(".github")
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, submission_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    submission_files_dict[relative_path] = f.read()
            except OSError as e:
                logger.warning("Could not read file %s: %s", file_path, e)

    return submission_files_dict


def __build_pipeline(args, include_feedback: bool, service: GithubActionService):
    pipeline = service.autograder_pipeline(
        args.template_preset, include_feedback, args.feedback_type
    )
    logger.info("Assignment config created: %s", pipeline)
    return pipeline


def __parser_values():
    args = parser.parse_args()

    if not args.app_token:
        args.app_token = args.github_token

    if args.feedback_type == "ai" and not args.openai_key:
        raise ValueError(
            "OpenAI API key is required for AI feedback mode in GitHub Actions. Please configure OPENAI_API_KEY as a secret."
        )

    return args


def __has_feedback(args_feedback: str | None):
    include_feedback = False
    if args_feedback is not None:
        val = str(args_feedback).strip().lower()
        if val not in ("true", "false"):
            raise ValueError(
                "Invalid value for --include-feedback. Allowed values: 'true' or 'false'."
            )
        include_feedback = val == "true"
    return include_feedback


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(main())
