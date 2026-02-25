"""
GitHub Action Adapter for Autograder.

This module provides the entry point for the GitHub Action adapter that integrates
with the autograder workflow to process student submissions and generate feedback.
"""

import logging
import os
from argparse import ArgumentParser
from .github_action_service import GithubActionService
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
parser.add_argument("--app_token", type=str, required=False, help="GitHub App Token")
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
    args = __parser_values()

    if args.template_preset == "custom":
        return

    include_feedback = __has_feedback(args.include_feedback)

    if args.openai_key:
        os.environ["OPENAI_API_KEY"] = args.openai_key

    service = GithubActionService(args.github_token, args.app_token)
    pipeline = __build_pipeline(args, include_feedback, service)
    grading_result = __retrieve_grading_score(args, service, pipeline)

    service.export_results(
        grading_result.final_score, include_feedback, grading_result.feedback
    )

def __retrieve_grading_score(args, service, pipeline):
    grading_result = service.run_autograder(pipeline, args.student_name).result
    if grading_result is None:
        raise Exception("Fail to get grading result")
    logger.info(
        "Final Score for %s: %s", args.student_name, grading_result.final_score
    )

    return grading_result

def __build_pipeline(args, include_feedback, service):
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
