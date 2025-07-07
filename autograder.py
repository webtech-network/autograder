from core.final_scorer import Scorer
import argparse
import os

parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")
args = parser.parse_args()

github_token = args.token
author = os.getenv("GITHUB_ACTOR")


scorer = Scorer.quick_build(author)


reporter = scorer.get_reporter(github_token, mode="ai")
reporter.create_report()
reporter.notify_classroom()
reporter.overwrite_report_in_repo(github_token)







