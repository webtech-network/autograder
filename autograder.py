import argparse
from grading.final_scorer import get_final_score
import grading.final_scorer as fs
from utils.result_exporter import notify_classroom
def parse_arguments():
    parser = argparse.ArgumentParser(description="Github Classroom HTML/CSS/JS autograder by Webtech Network")
    parser.add_argument("--html-weight", type=float, required=True, help="Weight for HTML grading")
    parser.add_argument("--css-weight", type=float, required=True, help="Weight for CSS grading")
    parser.add_argument("--js-weight", type=float, required=True, help="Weight for JavaScript grading")
    parser.add_argument("--grading-criteria", type=str, required=True, help="JSON string with grading criteria")
    parser.add_argument("--timeout", type=int, required=True, help="Timeout for grading execution in seconds")
    parser.add_argument("--token", type=str, required=True, help="Github Personal Acess Token (PAT)" )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    html_weight = args.html_weight
    css_weight = args.css_weight
    js_weight = args.js_weight
    grading_criteria = args.grading_criteria
    timeout = args.timeout
    token = args.token

    if html_weight+css_weight+js_weight != 100:
        raise ValueError("Weights must sum to 100")
    final_score = get_final_score(html_weight,css_weight,js_weight)

    print(f"Final score is {final_score}")

    notify_classroom(final_score,token)



