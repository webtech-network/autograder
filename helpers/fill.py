import json
import os

import argparse

from connectors.models.assignment_config import AssignmentConfig



def prepare_session(assignment_config, submission_files):
    """
    Receives all the files needed and places them in the correct directories for the grading job.
    """
    # Get the project root (two levels up from this file)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # Define paths for the directories that need to be cleaned, relative to project root
    validation_path = os.path.join(project_root, "autograder", "validation")
    request_bucket_path = os.path.join(project_root, "autograder", "request_bucket")
    validation_tests_path = os.path.join(validation_path, "tests")
    submission_path = os.path.join(request_bucket_path, "submission")

    # Ensure directories exist
    os.makedirs(validation_tests_path, exist_ok=True)
    os.makedirs(submission_path, exist_ok=True)
    os.makedirs(os.path.join(validation_tests_path, "results"), exist_ok=True)

    # Determine file extension based on test_framework
    framework = getattr(assignment_config, "test_framework", "pytest")
    ext = ".py" if framework == "pytest" else ".js" if framework == "jest" else ".json" if framework == "ai" else ".txt"

    # Place test files in /validation/tests
    test_files = assignment_config.test_files
    if test_files.test_base:
        with open(os.path.join(validation_tests_path, f"test_base{ext}"), "w", encoding="utf-8") as f:
            f.write(test_files.test_base)
    if test_files.test_bonus:
        with open(os.path.join(validation_tests_path, f"test_bonus{ext}"), "w", encoding="utf-8") as f:
            f.write(test_files.test_bonus)
    if test_files.test_penalty:
        with open(os.path.join(validation_tests_path, f"test_penalty{ext}"), "w", encoding="utf-8") as f:
            f.write(test_files.test_penalty)

    # Place other test files in /validation
    for filename, content in test_files.other_files.items():
        with open(os.path.join(validation_path, filename), "w", encoding="utf-8") as f:
            f.write(content)

    # Place config files in /request_bucket
    if assignment_config.criteria:
        with open(os.path.join(request_bucket_path, "criteria.json"), "w", encoding="utf-8") as f:
            json.dump(json.loads(assignment_config.criteria), f, ensure_ascii=False, indent=2)
    if assignment_config.feedback:
        with open(os.path.join(request_bucket_path, "feedback.json"), "w", encoding="utf-8") as f:
            json.dump(json.loads(assignment_config.feedback), f, ensure_ascii=False, indent=2)
    if assignment_config.ai_feedback:
        with open(os.path.join(request_bucket_path, "ai-feedback.json"), "w", encoding="utf-8") as f:
            json.dump(json.loads(assignment_config.ai_feedback), f, ensure_ascii=False, indent=2)
    if assignment_config.setup:
        with open(os.path.join(request_bucket_path, "autograder-setup.json"), "w", encoding="utf-8") as f:
            json.dump(json.loads(assignment_config.setup), f, ensure_ascii=False, indent=2)
    # Place submission files in /request_bucket/submission
    for filename, content in submission_files.items():
        with open(os.path.join(submission_path, filename), "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fills submission files.")
    parser.add_argument("preset",help="Preset name", type=str)
    parser.add_argument("--files",help="Submission files to send",type=str,required=False,default=None)
    args = parser.parse_args()
    if args.preset == "html-css-js":
        ass = AssignmentConfig.load_preset("html-css-js")
        print(ass)
        files = {
            "index.html":
                """<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <h1>Welcome to My Page</h1> <!-- ✅ Matches test requirement -->
            <p>This is a simple webpage.</p> <!-- ✅ Just needs a paragraph -->

            <button id="myButton">Click Me!</button> <!-- ✅ Button with correct ID & text -->

            <script src="script.js"></script>
        </body>
        </html>""",
            "style.css": """
                /* ✅ Background color applied */
            body {
                background-color: lightblue;
            }

            /* ✅ <h1> has a color */
            h1 {
                color: darkblue;
            }
                """,
            "script.js":
                """
                // ✅ Select the button and add a click event listener
        document.getElementById("myButton").addEventListener("click", function() {
            this.textContent = "Clicked!"; // ✅ Changes button text on click
        });
                """
        }
        submission_file = {args.files:files[args.files]} if args.files else files
        prepare_session(ass,submission_file)

