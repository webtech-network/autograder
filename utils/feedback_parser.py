import ast, os, json

def extract_docstring_feedback(file_path, category):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    tests = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            docstring = ast.get_docstring(node)
            test_id = f"grading/tests/{os.path.basename(file_path)}::{node.name}"

            pass_msg = "✅ Sucesso"
            fail_msg = "❌ Falhou"

            if docstring:
                for line in docstring.splitlines():
                    if line.strip().startswith("pass:"):
                        pass_msg = line.strip().split("pass:", 1)[1].strip()
                    elif line.strip().startswith("fail:"):
                        fail_msg = line.strip().split("fail:", 1)[1].strip()

            tests.append({test_id: [pass_msg, fail_msg]})
    return category, tests

def generate_feedback_from_docstrings():
    files = [
        ("grading/tests/test_base.py", "base_tests"),
        ("grading/tests/test_bonus.py", "bonus_tests"),
        ("grading/tests/test_penalty.py", "penalty_tests")
    ]

    all_feedback = {}

    for file, category in files:
        key, values = extract_docstring_feedback(file, category)
        all_feedback[key] = values

    with open("feedback.json", "w", encoding="utf-8") as f:
        json.dump(all_feedback, f, indent=2, ensure_ascii=False)

    print("✅ feedback.json file generated using docstrings!")

