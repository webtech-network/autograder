import logging
from argparse import ArgumentParser
from connectors.adapters.github_action_adapter.github_adapter import GithubAdapter
from connectors.models.assignment_config import AssignmentConfig

logger = logging.getLogger(__name__)

parser = ArgumentParser(description="GitHub Action Adapter for Autograder")
parser.add_argument("--github-token", type=str, required=True, help="GitHub Token")
parser.add_argument("--template-preset", type=str, required=True, help="The grading preset to use (e.g., api, html, python, etc.)")
parser.add_argument("--student-name", type=str, required=True, help="The name of the student")
parser.add_argument("--feedback-type", type=str, default="default",help="The type of feedback to provide (default or ai)")
parser.add_argument("--custom-template", type=str, required=False, help="Test Files for the submission (in case of custom preset)")
parser.add_argument("--app_token", type=str, required=False, help="GitHub App Token")
parser.add_argument("--openai-key", type=str, required=False, help="OpenAI API key for AI feedback (required only for AI feedback mode)")
parser.add_argument("--include-feedback", type=str, required=False, help="Whether to include/generate feedback (true/false).")

async def main():
    """
    This is the entry point for the GitHub Action adapter. 
    This makes the Adapter accessible to the GitHub Action workflow, that will run it in the entrypoint.sh script with all arguments passed to it.
    """
    args = parser.parse_args()
    github_token = args.github_token
    if not args.app_token:
        args.app_token = github_token
    template_preset = args.template_preset
    student_name = args.student_name
    feedback_type = args.feedback_type
    
    # Validate that AI feedback has required credentials
    if feedback_type == "ai":
        if not args.openai_key:
            raise ValueError("OpenAI API key is required for AI feedback mode in GitHub Actions. Please configure OPENAI_API_KEY as a secret.")
    
    adapter = GithubAdapter(github_token,args.app_token)
    if args.template_preset == "custom":
        # Validate and load the custom template preset
        pass
    else:
        assignment_config = adapter.create_assigment_config(template_preset)
        logger.info(f"Assignment config created: {assignment_config}")

    # Parse include_feedback value
    include_feedback = False
    if args.include_feedback is not None:
        val = str(args.include_feedback).strip().lower()
        if val not in ("true", "false"):
            raise ValueError("Invalid value for --include-feedback. Allowed values: 'true' or 'false'.")
        include_feedback = (val == "true")

    # GitHub Actions must provide credentials for AI feedback
    adapter.create_request(
        submission_files=None,
        assignment_config=assignment_config,
        student_name=student_name,
        student_credentials=github_token,
        feedback_mode=feedback_type,
        openai_key=args.openai_key,
        include_feedback=include_feedback,
    )

    adapter.run_autograder()

    logger.info(f"Final Score for {student_name}: {adapter.autograder_response.final_score}")

    adapter.export_results()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    asyncio.run(main())
