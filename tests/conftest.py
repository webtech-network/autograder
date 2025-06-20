import pytest
from bs4 import BeautifulSoup
import os

# Helper function to parse HTML content using BeautifulSoup
# This function should ideally take the submission file path as an argument,
# which would be passed from the test function.
def parse_html(file_path="submission/index.html"):
    """
    Parses an HTML file using BeautifulSoup.
    """
    if not os.path.exists(file_path):
        pytest.fail(f"Submission HTML file not found at: {file_path}")
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            return BeautifulSoup(file.read(), "html.parser")
    except Exception as e:
        pytest.fail(f"Error parsing HTML file '{file_path}': {e}")

# Helper function to parse a CSS file
def parse_css(file_path="submission/style.css"):
    """
    Reads the content of a CSS file.
    """
    if not os.path.exists(file_path):
        pytest.fail(f"Submission CSS file not found at: {file_path}")
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        pytest.fail(f"Error reading CSS file '{file_path}': {e}")

# Helper function to parse a JavaScript file
def parse_js(file_path="submission/script.js"):
    """
    Reads the content of a JavaScript file.
    """
    if not os.path.exists(file_path):
        pytest.fail(f"Submission JavaScript file not found at: {file_path}")
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        pytest.fail(f"Error reading JavaScript file '{file_path}': {e}")

@pytest.fixture(autouse=True)
def quantitative_result_recorder(request):
    """
    Fixture to allow individual quantitative tests to report their actual_count.
    The data is attached to the test report via `request.node.user_properties`.
    """
    def record_count(actual_count: int):
        # Record only the actual count
        request.node.user_properties.append(('quantitative_result', actual_count))
    return record_count
