# /autograder/core/test_generation/test_library/css_tests.py
import os
import re

# --- Helper Functions ---

def parse_css(submission_path):
    """Parses the student's style.css file."""
    css_path = os.path.join(submission_path, 'style.css')
    try:
        with open(css_path, 'r', encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""

# --- Validation Functions ---

# Syntax & Best Practices
def check_uses_shorthand_properties(css_content):
    assert "margin:" in css_content or "padding:" in css_content or "font:" in css_content, "Shorthand properties for margin, padding, or font are not used."

def check_uses_css_variables(css_content):
    assert re.search(r'--[\w-]+:', css_content), "No CSS variables (custom properties) found."

def check_no_overqualified_selectors(css_content):
    # Simple check for selectors with more than 2 levels of depth
    for line in css_content.splitlines():
        if '{' in line:
            selector = line.split('{')[0].strip()
            if len(selector.split()) > 3:
                assert False, f"Overqualified selector detected: '{selector}'"

def check_no_redundant_rules(css_content):
    rules = re.findall(r'([^{]+){([^}]+)}', css_content)
    selectors = [r[0].strip() for r in rules]
    assert len(selectors) == len(set(selectors)), "Duplicate CSS selectors found."

def check_uses_consistent_units(css_content):
    units = set(re.findall(r'\d+(px|em|rem|%|vw|vh)', css_content))
    assert len(units) <= 2, f"Inconsistent units used. Found: {', '.join(units)}"

def check_no_important(css_content):
    assert "!important" not in css_content, "The use of '!important' was found."

# Layout & Responsivity
def check_uses_flexbox_or_grid(css_content):
    assert "display: flex" in css_content or "display: grid" in css_content, "Neither Flexbox nor Grid is used for layout."

def check_uses_media_queries(css_content):
    assert "@media" in css_content, "No media queries found for responsive design."

def check_uses_responsive_typography(css_content):
    assert re.search(r'font-size:\s*\d+(rem|em|vw|%)', css_content) or 'clamp(' in css_content, "Responsive typography (rem, em, vw, clamp) not used."

# Styling & Frameworks
def check_uses_dark_mode(css_content):
    assert "@media (prefers-color-scheme: dark)" in css_content, "No dark mode support detected."

def check_has_custom_font(css_content):
    assert "@import url" in css_content or "@font-face" in css_content, "No custom font import found."

def check_has_animation(css_content):
    assert "@keyframes" in css_content or "animation:" in css_content, "No CSS animations found."

def check_uses_bootstrap_components(soup, components):
    for component_class in components:
        assert soup.find(class_=component_class) is not None, f"Required Bootstrap component class '{component_class}' not found."

def check_uses_bootstrap_grid(soup):
    assert soup.find(class_="row") and soup.find(lambda c: c and c.startswith("col-")), "Bootstrap grid system ('row' and 'col-*') not used."
