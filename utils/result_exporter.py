import os
from github import Github
import json

def notify_classroom(final_score,token):
    # Check if the final_score is provided and is between 0 and 100
    if final_score < 0 or final_score > 100:
        print("Invalid final score. It should be between 0 and 100.")
        return

    # Retrieve the GitHub token and repository information from environment variables

    repo_name = os.getenv("GITHUB_REPOSITORY")
    if not repo_name:
        print("Repository information is missing.")
        return

    # Create the GitHub client using the token
    g = Github(token)
    repo = g.get_repo(repo_name)
    
    # Get the workflow run ID
    run_id = os.getenv("GITHUB_RUN_ID")
    if not run_id:
        print("Run ID is missing.")
        return
    print(f"run_id -> [{run_id}]")

    # Fetch the workflow run
    workflow_run = repo.get_workflow_run(int(run_id))
    
    # Find the check suite run ID
    check_suite_url = workflow_run.check_suite_url
    check_suite_id = int(check_suite_url.split('/')[-1])

    # Get the check runs for this suite
    check_runs = repo.get_check_suite(check_suite_id)
    check_run = next((run for run in check_runs.get_check_runs() if run.name == "run-tests"), None)
    for run in check_runs.get_check_runs():
        print(run.name)
    if not check_run:
        print("Check run not found.")
        return
    print(f"Check run ID -> {check_run.id}")
    # Create a summary for the final grade
    text = f"Final Score: {format(final_score,".2f")}/100"

    # Update the check run with the final score
    check_run.edit(
        name="Autograding",
        output={
            "title": "Autograding Result",
            "summary": text,
            "text": json.dumps({ "totalPoints": format(final_score,".2f"), "maxPoints": 100 }),
            "annotations": [{
                "path": ".github",
                "start_line": 1,
                "end_line": 1,
                "annotation_level": "notice",
                "message": text,
                "title": "Autograding complete"
            }]
        }
    )

    print(f"Final grade updated: {format(final_score,".2f")}/100")
    
if __name__ == "__main__": 
    token = input()
    notify_classroom(95,token)