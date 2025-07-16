from core.final_scorer import Scorer
import argparse
import os

parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")
parser.add_argument("--redis-token", type=str, required=True, help="Upstash Redis REST token")
parser.add_argument("--redis-url", type=str, required=True, help="Upstash Redis REST URL")
parser.add_argument("--openai-key", type=str, required=True, help="OpenAI API key")
args = parser.parse_args()



github_token = args.token
author = os.getenv("GITHUB_ACTOR")


scorer = Scorer.quick_build(author,redis_url = args.redis_url, redis_token = args.redis_token)
print("Final Score is: ", scorer.get_final_score())

reporter = scorer.get_reporter(github_token,args.openai_key, mode="ai")
print(reporter._assemble_user_prompt())
print(reporter.overwrite_report_in_repo(new_content=reporter.generate_feedback()))
print("END________________________________")