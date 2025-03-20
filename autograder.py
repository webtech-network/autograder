import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Github Classroom HTML/CSS/JS autograder by Webtech Network")
    parser.add_argument("--html-weight", type=float, required=True, help="Weight for HTML grading")
    parser.add_argument("--css-weight", type=float, required=True, help="Weight for CSS grading")
    parser.add_argument("--js-weight", type=float, required=True, help="Weight for JavaScript grading")
    parser.add_argument("--grading-criteria", type=str, required=True, help="JSON string with grading criteria")
    parser.add_argument("--timeout", type=int, required=True, help="Timeout for grading execution in seconds")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()