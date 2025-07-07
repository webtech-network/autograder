from core.final_scorer import Scorer
import argparse
from core.report.result_exporter import notify_classroom
from core.report.commit_report import overwrite_report_in_repo
import os

parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")
args = parser.parse_args()

github_token = args.token
author = os.getenv("GITHUB_ACTOR")


scorer = Scorer.create_with_scores("tests",github_token,author,"test_base.py","test_bonus.py","test_penalty.py")
final_score = scorer.final_score


feedback = scorer.create_feedback()
overwrite_report_in_repo(github_token,new_content=feedback)

notify_classroom(final_score, github_token)


