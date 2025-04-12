
import pytest
from bs4 import BeautifulSoup

def parse_html():
    with open('submission/index.html', 'r', encoding='utf-8') as file:
        return BeautifulSoup(file.read(), 'html.parser')

def parse_css():
    with open('submission/style.css', 'r', encoding='utf-8') as file:
        return file.read()

def parse_js():
    with open('submission/script.js', 'r', encoding='utf-8') as file:
        return file.read()


# === PENALTY TESTS (INVERTED LOGIC) ===

# ❌ 1. Use of <br> instead of CSS spacing
def test_html_use_of_br_tag():
    soup = parse_html()
    assert soup.find('br') is not None, "No <br> tag found (this test should pass when <br> is used)."

# ❌ 2. Use of inline styles (e.g., style="...")
def test_css_inline_styles():
    soup = parse_html()
    assert soup.find(attrs={"style": True}) is not None, "No inline styles found (should pass if inline styles exist)."

# ❌ 3. Overuse of <div> without semantic meaning
def test_html_overuse_of_divs():
    soup = parse_html()
    divs = soup.find_all('div')
    assert len(divs) > 10, "Too few <div> tags for overuse penalty (needs > 10)."

# ❌ 4. JavaScript in HTML (inline script tags)
def test_html_inline_script_tags():
    soup = parse_html()
    script_tags = soup.find_all('script')
    for script in script_tags:
        if not script.get('src'):
            assert True
            return
    assert False, "No inline <script> tag found."

# ❌ 5. Use of <center> for alignment (deprecated and undesired)
def test_html_use_of_center_tag():
    soup = parse_html()
    assert soup.find('center') is not None, "No <center> tag found."


# ❌ 7. Use of alert() in JavaScript
def test_html_alert_usage():
    js = parse_js()
    assert "alert(" in js, "No use of alert() found in JS."

# ❌ 8. Use of document.write()
def test_html_document_write():
    js = parse_js()
    assert "document.write(" in js, "No use of document.write() found."

# ❌ 9. Use of deprecated HTML tags (e.g., <u>)
def test_html_deprecated_u_tag():
    soup = parse_html()
    assert soup.find('u') is not None, "No deprecated <u> tag found."

# ❌ 10. Use of hardcoded width/height in HTML
def test_html_hardcoded_image_dimensions():
    soup = parse_html()
    imgs = soup.find_all('img')
    for img in imgs:
        if img.get('width') or img.get('height'):
            assert True
            return
    assert False, "No hardcoded width or height attributes found on images."

# 2. Test if `!important` is used
def test_html_no_important_usage():
    css_content = parse_css()
    # Check for `!important` in the CSS code
    assert "!important" in css_content, "Didn't Found !important in the CSS."

def test_html_forbidden_b_tag():
    soup = parse_html()
    # Ensure no <b> tag is present
    assert soup.find('b') is not None, "Found forbidden <b> tag"

def test_html_forbidden_i_tag():
    soup = parse_html()
    # Ensure no <i> tag is present
    assert soup.find('i') is not None, "Found forbidden <i> tag"

def test_html_forbidden_font_tag():
    soup = parse_html()
    # Ensure no <font> tag is present
    assert soup.find('font') is not None, "Found forbidden <font> tag"

def test_html_forbidden_marquee_tag():
    soup = parse_html()
    # Ensure no <marquee> tag is present
    assert soup.find('marquee') is not None, "Found forbidden <marquee> tag"

def test_html_forbidden_center_tag():
    soup = parse_html()
    # Ensure no <center> tag is present
    assert soup.find('center') is not None, "Found forbidden <center> tag"