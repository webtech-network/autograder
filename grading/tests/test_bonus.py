
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


# === BONUS TESTS ===

# --- HTML BONUS TESTS ---

def test_html_favicon_link():
    soup = parse_html()
    assert soup.find('link', rel='icon') is not None, "Favicon is not included in the <head>."

def test_html_section_ids_are_meaningful():
    soup = parse_html()
    sections = soup.find_all('section')
    for section in sections:
        sid = section.get('id')
        assert sid is not None and '-' in sid, "Section ID is missing or not meaningful (use kebab-case)."

def test_html_article_or_aside_used():
    soup = parse_html()
    assert soup.find('article') or soup.find('aside'), "No <article> or <aside> tags found."


# --- CSS BONUS TESTS ---

def test_html_dark_mode_support():
    css = parse_css()
    assert '@media (prefers-color-scheme: dark)' in css, "No dark mode support detected."

def test_html_custom_font_imported():
    css = parse_css()
    assert '@import url(' in css or 'fonts.googleapis.com' in css, "Custom font not imported."

def test_css_css_animation():
    css = parse_css()
    assert '@keyframes' in css or 'animation:' in css, "No CSS animation detected."

def test_html_responsive_typography():
    css = parse_css()
    assert 'clamp(' in css or 'vw' in css or 'rem' in css, "Responsive typography not found (use clamp, rem, vw, etc.)."


# --- JS BONUS TESTS ---

def test_js_js_uses_template_literals():
    js = parse_js()
    assert '`' in js and '${' in js, "No usage of template literals found in JavaScript."

def test_html_local_or_session_storage():
    js = parse_js()
    assert 'localStorage.' in js or 'sessionStorage.' in js, "No use of localStorage or sessionStorage."

def test_html_interaction_feedback():
    js = parse_js()
    keywords = ['classList.add', 'innerHTML', 'textContent', 'disabled', 'toggle']
    assert any(k in js for k in keywords), "No dynamic feedback behavior found on user interaction."

def test_html_form_validation_logic():
    js = parse_js()
    assert 'checkValidity' in js or 'regex' in js or '.test(' in js, "No form validation logic found."

def test_html_modular_code_structure():
    js = parse_js()
    assert 'export ' in js or 'import ' in js, "JavaScript modular code structure (ES Modules) not detected."

# 13. Test for proper use of array methods (e.g., map, filter, reduce)
def test_html_array_methods():
    js_content = parse_js()
    # Ensure that array methods like map, filter, reduce are used instead of traditional loops
    assert "map(" in js_content or "filter(" in js_content or "reduce(" in js_content, "Array methods like map, filter, or reduce are not used."

# 10. Test for preventing memory leaks
def test_html_memory_leaks():
    js_content = parse_js()
    # Ensure that event listeners or intervals are properly cleaned up to avoid memory leaks
    assert ".removeEventListener" in js_content or "clearInterval" in js_content or "clearTimeout" in js_content, "Memory leaks may occur due to unremoved event listeners or intervals."

# 6. Test for Minification
def test_css_css_minification():
    css_content = parse_css()
    # Ensure that the CSS is minified (no extra spaces or line breaks)
    assert css_content == css_content.replace(" ", "").replace("\n", ""), "CSS is not minified."

def test_html_open_graph_description_tag():
    soup = parse_html()
    # Ensure Open Graph meta description tag is present
    meta_tag = soup.find('meta', attrs={"property": "og:description"})
    assert meta_tag is not None, "Missing Open Graph <meta property='og:description'> tag"

def test_html_open_graph_title_tag():
    soup = parse_html()
    # Ensure Open Graph meta title tag is present
    meta_tag = soup.find('meta', attrs={"property": "og:title"})
    assert meta_tag is not None, "Missing Open Graph <meta property='og:title'> tag"

def test_html_meta_description():
    soup = parse_html()
    # Ensure the meta description tag is present
    meta_tag = soup.find('meta', attrs={"name": "description"})
    assert meta_tag is not None, "Missing <meta name='description'> tag"

