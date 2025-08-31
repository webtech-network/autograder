from argparse import ArgumentParser
from connectors.adapters.github_action_adapter.github_adapter import GithubAdapter
from connectors.models.assignment_config import AssignmentConfig
from connectors.utils.load_preset import load_preset
parser = ArgumentParser(description="GitHub Action Adapter for Autograder")
parser.add_argument("--github-token", type=str, required=True, help="GitHub Token")
parser.add_argument("--template-preset", type=str, required=True, help="The grading preset to use (e.g., api, html, python, etc.)")
parser.add_argument("--student-name", type=str, required=True, help="The name of the student")
parser.add_argument("--feedback-type", type=str, default="default",help="The type of feedback to provide (default or ai)")
parser.add_argument("--custom-template", type=str, required=False, help="Test Files for the submission (in case of custom preset)")
parser.add_argument("--app_token", type=str, required=False, help="GitHub App Token")
parser.add_argument("--openai-key", type=str, required=False, help="OpenAI API key for AI feedback")
parser.add_argument("--redis-url", type=str, required=False, help="Redis URL for AI feedback")
parser.add_argument("--redis-token", type=str, required=False, help="Redis token for AI feedback")

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
    if feedback_type == "ai":
        if not args.openai_key or not args.redis_url or not args.redis_token:
            raise ValueError("OpenAI key, Redis URL, and Redis token are required for AI feedback.")
    adapter = GithubAdapter(github_token,args.app_token)
    if args.template_preset == "custom":
        assignment_config = adapter.create_custom_assignment_config(test_files=None, criteria=None, feedback=None, ai_feedback=None, setup=None, test_framework=test_framework)
    else:
        assignment_config = adapter.create_assigment_config(template_preset)
        print(assignment_config)

    adapter.create_request(submission_files=None,assignment_config=assignment_config,student_name=student_name,student_credentials=github_token,feedback_mode=feedback_type,openai_key=args.openai_key,redis_url=args.redis_url,redis_token=args.redis_token)

    adapter.run_autograder()

    print(f"Final Score for {student_name}: {adapter.autograder_response.final_score}")

    adapter.export_results()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
