from core.final_scorer import Scorer
import argparse
import os

from core.report.ai_reporter import AIReporter

parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")
parser.add_argument("--autograder-bot-token", type=str, required=False, help="Autograder App token")
parser.add_argument("--redis-token", type=str, required=True, help="Upstash Redis REST token")
parser.add_argument("--redis-url", type=str, required=True, help="Upstash Redis REST URL")
parser.add_argument("--openai-key", type=str, required=True, help="OpenAI API key")
args = parser.parse_args()



github_token = args.token
author = os.getenv("GITHUB_ACTOR")
autograder_bot_token = args.autograder_bot_token
if not autograder_bot_token:
    autograder_bot_token = github_token  # Use the same token if autograder bot token is not provided
scorer = Scorer.quick_build(author,redis_url = args.redis_url, redis_token = args.redis_token)
print("Final Score is: ", scorer.get_final_score())

reporter = scorer.get_reporter(autograder_bot_token,args.openai_key, mode="ai")
feedback = reporter.generate_feedback()
if isinstance(reporter,AIReporter):
    print(reporter.assemble_user_prompt())
reporter.notify_classroom(github_token)
reporter.overwrite_report_in_repo(new_content=feedback)







