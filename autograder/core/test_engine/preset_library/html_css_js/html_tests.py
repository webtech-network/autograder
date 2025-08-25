# /autograder/core/test_generation/test_library/html_tests.py
import os
from bs4 import BeautifulSoup

# --- Helper Functions ---

def parse_html(submission_path):
    """Parses the student's index.html file."""
    html_path = os.path.join(submission_path, 'index.html')
    try:
        with open(html_path, 'r', encoding="utf-8") as file:
            return BeautifulSoup(file.read(), "html.parser")
    except FileNotFoundError:
        return None

# --- Validation Functions ---

# Structure & Boilerplate
def check_has_tag(soup, tag):
    assert soup.find(tag) is not None, f"The <{tag}> tag is missing."

def check_has_meta_tag(soup, attrs):
    assert soup.find('meta', attrs=attrs) is not None, f"Missing meta tag with attributes: {attrs}"

def check_is_css_linked(soup):
    link = soup.find("link", {"rel": "stylesheet"})
    assert link is not None, "The CSS file is not linked."
    assert link.get("href"), "The linked CSS file is missing an href attribute."

def check_has_favicon(soup):
    assert soup.find('link', rel='icon') is not None, "Favicon is not linked in the <head>."

# Content & Semantics
def check_tag_contains_text(soup, tag, text):
    element = soup.find(tag)
    assert element and text in element.get_text(), f"The <{tag}> tag does not contain the text '{text}'."

def check_has_semantic_tags(soup):
    assert soup.find('article') or soup.find('aside'), "No <article> or <aside> tags found."

def check_has_meaningful_ids(soup):
    sections = soup.find_all('section')
    for section in sections:
        sid = section.get('id')
        assert sid and '-' in sid, "A section ID is missing or not in kebab-case."

# Accessibility
def check_images_have_alt(soup):
    for img in soup.find_all('img'):
        assert img.has_attr('alt'), f"Image '{img.get('src', 'N/A')}' is missing an 'alt' attribute."

def check_inputs_have_labels(soup):
    for input_tag in soup.find_all('input'):
        if input_tag.get('type') not in ['hidden', 'submit', 'button', 'reset']:
            assert soup.find('label', attrs={'for': input_tag.get('id')}), f"Input with id '{input_tag.get('id')}' is missing a corresponding <label>."

# Code Quality & Best Practices
def check_no_unclosed_tags(html_content):
    # This is a simplified check. A more robust solution might involve an HTML validator library.
    soup = BeautifulSoup(html_content, "html.parser")
    assert str(soup) == html_content, "Potential unclosed tags detected."

def check_no_improper_nesting(soup):
    for ul in soup.find_all('ul'):
        for child in ul.children:
            if child.name is not None and child.name != 'li':
                assert False, f"Invalid tag <{child.name}> found directly inside <ul>."

def check_no_inline_styles(soup):
    assert soup.find(style=True) is None, "Inline style attribute found."

def check_no_deprecated_tags(soup, forbidden_tags):
    for tag in forbidden_tags:
        assert soup.find(tag) is None, f"Deprecated <{tag}> tag was found."

def check_no_hardcoded_dimensions(soup):
    for img in soup.find_all('img'):
        assert not img.has_attr('width') and not img.has_attr('height'), f"Image '{img.get('src')}' has hardcoded dimensions."

# Quantitative Analysis
def check_tag_count(soup, tag, min_count=None, max_count=None, exact_count=None):
    count = len(soup.find_all(tag))
    if min_count is not None:
        assert count >= min_count, f"Expected at least {min_count} <{tag}> tags, but found {count}."
    if max_count is not None:
        assert count <= max_count, f"Expected at most {max_count} <{tag}> tags, but found {count}."
    if exact_count is not None:
        assert count == exact_count, f"Expected exactly {exact_count} <{tag}> tags, but found {count}."
