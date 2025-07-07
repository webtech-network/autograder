from core.final_scorer import Scorer
import argparse
import os

parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")
parser.add_argument("--redis-token", type=str, required=True, help="Upstash Redis REST token")
parser.add_argument("--redis-url", type=str, required=True, help="Upstash Redis REST URL")
parser.add_argument("--openai-key", type=str, required=True, help="OpenAI API key")
args = parser.parse_args()

env_vars = {
    "UPSTASH_REDIS_REST_TOKEN": args.redis_token,
    "UPSTASH_REDIS_REST_URL": args.redis_url,
    "OPENAI_API_KEY": args.openai_key
}

# Iterate over the dictionary and set each environment variable.
for key, value in env_vars.items():
    os.environ[key] = value
    print(f"Set environment variable: {key}")

github_token = args.token
author = os.getenv("GITHUB_ACTOR")


scorer = Scorer.quick_build(author)


reporter = scorer.get_reporter(github_token, mode="ai")
reporter.create_report()
reporter.notify_classroom()
reporter.overwrite_report_in_repo(github_token)







