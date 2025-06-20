from openai import OpenAI
client = OpenAI(api_key = "")


candidate_code = """
def add(a, b):
    return a + b
"""

perfect_code = """
def add(a, b):
    # Handles floats and integers and raises TypeError on invalid input
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Inputs must be numbers")
    return a + b
"""

test_results = {
    "base": {
        "test_add_positive_numbers": "passed",
        "test_add_negative_numbers": "failed"
    },
    "bonus": {
        "test_add_floats": "passed"
    },
    "penalty": {
        "test_add_strings": "passed"
    },
    "score": 65
}

system_prompt = (
    "You are an expert code reviewer. You just received a candidate's solution "
    "for a code challenge. Your job is to give friendly, human, motivating feedback based on which "
    "unit tests passed and failed. You will compliment what's good, highlight issues in a kind way, "
    "and encourage the candidate to improve. Your tone is casual, empathetic,human-like and constructive. "
    "Mention the types of tests: base (essential), bonus (nice-to-have), and penalty (bad practices)."
)

user_prompt = f"""
Here is the candidate's code:
{candidate_code}

Here is the perfect solution:
{perfect_code}

Test results:
Base tests:
{test_results['base']}

Bonus tests:
{test_results['bonus']}

Penalty tests:
{test_results['penalty']}

Candidate's score: {test_results['score']}%

Please provide human-friendly feedback.
"""

resp = client.responses.create(
  model="gpt-4.1",
  tools=[
    {
      "type": "code_interpreter",
      "container": { "type": "auto" }
    }
  ],
  instructions=system_prompt,
  input=user_prompt,
)

print(resp.output_text)

