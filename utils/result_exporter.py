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
                "filename": "tests/test_css.py",
                "line_no": 7,
                "duration": 0.0001458939999992026,
                "score": 11.11111111111111
            }
        ],
        "max_score": 100
    }
