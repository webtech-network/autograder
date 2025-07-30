from argparse import ArgumentParser
from connectors.adapters.github_action_adapter.github_adapter import GithubAdapter
from connectors.utils.load_preset import load_preset
parser = ArgumentParser(description="GitHub Action Adapter for Autograder")
parser.add_argument("--github_token", type=str, required=True, help="GitHub Token")
parser.add_argument("--app_token", type=str, required=False, help="GitHub App Token")
parser.add_argument("--test_framework", type=str, required=True, help="The test framework to use (e.g., pytest)")
parser.add_argument("--grading-preset", type=str, required=True, help="The grading preset to use (e.g., api, html, python, etc.)")
parser.add_argument("--student_name", type=str, required=True, help="The name of the student")
parser.add_argument("--feedback_type", type=str, default="default",help="The type of feedback to provide (default or ai)")
parser.add_argument("--openai_key", type=str, required=False, help="OpenAI API key for AI feedback")
parser.add_argument("--redis_url", type=str, required=False, help="Redis URL for AI feedback")
parser.add_argument("--redis_token", type=str, required=False, help="Redis token for AI feedback")

if __name__ == "__main__":
    """
    This is the entry point for the GitHub Action adapter. 
    This makes the Adapter accessible to the GitHub Action workflow, that will run it in the entrypoint.sh script with all arguments passed to it.
    """
    args = parser.parse_args()
    github_token = args.github_token
    if not args.app_token:
        args.app_token = github_token
    test_framework = args.test_framework
    student_name = args.student_name
    feedback_type = args.feedback_type
    if feedback_type == "ai":
        if not args.openai_key or not args.redis_url or not args.redis_token:
            raise ValueError("OpenAI key, Redis URL, and Redis token are required for AI feedback.")
    adapter = GithubAdapter.create(test_framework,
                                   student_name,
                                   feedback_type,
                                   github_token,
                                   app_token=args.app_token,
                                   openai_key=args.openai_key,
                                   redis_url=args.redis_url,
                                   redis_token=args.redis_token
                                   )
    #TODO: Look for a criteria.json or feedback.json file in the presets directory
    load_preset(args.grading_preset)
    adapter.run_autograder()
    print(f"Final Score for {student_name}: {adapter.autograder_response.final_score}")
    adapter.notify_classroom()
    adapter.commit_feedback()
