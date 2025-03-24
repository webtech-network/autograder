import os
import json
import base64

def create_dict(final_score):
    status = "passed" if final_score >= 60 else "failed"
    result = {
        "version": 3,
        "status": status,
        "tests": [
            {
                "name": "HTML/CSS/JS",
                "status": "pass",
                "test_code": 'assert "background-color" in css, "No background color set for <body>."',
                "task_id": 0,
                "filename": "autograder.py",
                "line_no": 7,
                "duration": 0.0001458939999992026,
                "score": final_score
            }
        ],
        "max_score": 100
    }

    return result

def encode_result(result):
    encoded_data = base64.b64encode(json.dumps(result).encode()).decode()
    return encoded_data
def export_result(encoded_data):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"result={encoded_data}\n")


def export(final_score):
    result_dict = create_dict(final_score)
    result_dict = encode_result(result_dict)
    export_result(result_dict)