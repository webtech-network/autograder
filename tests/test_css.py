import pytest
from bs4 import BeautifulSoup

# Helper function to parse HTML content and extract the linked CSS file
def parse_html():
    with open('index.html', 'r') as file:
        html_content = file.read()
    return BeautifulSoup(html_content, "html.parser")

# Helper function to parse the CSS file
def parse_css():
    with open('style.css', 'r') as file:
        return file.read()

# 1. Test if the CSS file is correctly linked
def test_css_linked():
    soup = parse_html()
    # Ensure the CSS file is linked in the <head> using <link rel="stylesheet">
    link = soup.find("link", {"rel": "stylesheet"})
    assert link is not None, "The CSS file is not linked."
    assert link["href"] == "style.css", "CSS file is incorrectly linked."

# 2. Test if `!important` is used
def test_no_important_usage():
    css_content = parse_css()
    # Check for `!important` in the CSS code
    assert "!important" not in css_content, "Found !important in the CSS."

# 3. Test for Shorthand CSS properties (e.g., margin, padding)
def test_shorthand_properties():
    css_content = parse_css()
    # Check for shorthand properties like margin, padding, etc.
    assert "margin:" in css_content or "padding:" in css_content, "Missing shorthand for margin or padding."

# 4. Test for the presence of CSS Variables
def test_css_variables():
    css_content = parse_css()
    # Check if CSS variables are used (e.g., --primary-color)
    assert "--primary-color" in css_content or "--secondary-color" in css_content, "Missing CSS variable for colors."

# 5. Test if the layout uses Flexbox or Grid (modern layout techniques)
def test_layout_method():
    css_content = parse_css()
    # Ensure that flexbox or grid is used in layout
    assert "display: flex" in css_content or "display: grid" in css_content, "Neither flexbox nor grid is used for layout."

# 6. Test for Minification
def test_css_minification():
    css_content = parse_css()
    # Ensure that the CSS is minified (no extra spaces or line breaks)
    assert css_content == css_content.replace(" ", "").replace("\n", ""), "CSS is not minified."

# 7. Test if CSS selectors are not overqualified
def test_no_overqualified_selectors():
    css_content = parse_css()
    # Ensure that the CSS selectors are not overqualified (i.e., too specific)
    selectors = [selector.strip() for selector in css_content.split(",")]
    for selector in selectors:
        assert selector.count(" ") <= 2, f"Overqualified selector detected: {selector}"

# 8. Test for External CSS Links (No inline CSS)
def test_external_css_only():
    soup = parse_html()
    # Ensure there is no inline CSS in the HTML (should use external CSS only)
    style_tag = soup.find("style")
    assert style_tag is None, "Inline CSS is present. Use external stylesheets only."

# 9. Test for Media Queries (Responsive design)
def test_media_queries():
    css_content = parse_css()
    # Ensure that media queries are present for responsiveness
    assert "@media" in css_content, "Missing media queries for responsive design."

# 10. Test for No Redundant or Duplicate Rules
def test_no_redundant_rules():
    css_content = parse_css()
    # Ensure that there are no duplicate CSS rules for the same selector
    rules = css_content.split("}")
    selectors = set()
    for rule in rules:
        selector = rule.split("{")[0].strip()
        if selector:
            assert selector not in selectors, f"Duplicate rule for {selector} found."
            selectors.add(selector)

# 11. Test for Consistent Units
def test_consistent_units():
    css_content = parse_css()
    # Ensure consistent use of units (e.g., rem, em, px, etc.)
    assert "rem" in css_content or "em" in css_content or "px" in css_content, "Inconsistent use of CSS units."
