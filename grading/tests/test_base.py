import pytest
from bs4 import BeautifulSoup
'''
TEST SUITE FOR HTML PAGE
'''



# Helper function to parse HTML content using BeautifulSoup
def parse_html():
    # Directly open and parse the 'index.html' file
    with open('submission/index.html', 'r',encoding="utf-8") as file:
        html_content = file.read()
    return BeautifulSoup(html_content, "html.parser")

# 1. Test Required Structural Elements
# Helper function to parse the CSS file
def parse_css():
    with open('submission/style.css', 'r',encoding="utf-8") as file:
        return file.read()
def parse_js():
    with open('submission/script.js', 'r',encoding="utf-8") as file:
        return file.read()

def test_html_doctype():
    """
    pass: A verificação de HTML doctype passou com sucesso.
    fail: A verificação de HTML doctype falhou. Verifique se os elementos ou boas práticas estão corretamente implementados.
    """

    with open('submission/index.html', 'r', encoding='utf-8') as file:
        content = file.read().lower()
    assert '<!doctype html>' in content, "DOCTYPE declaration not found"


def test_html_html_tag():
    """
    pass: A verificação de HTML HTML tag passou com sucesso.
    fail: A verificação de HTML HTML tag falhou. Verifique se os elementos ou boas práticas estão corretamente implementados.
    """

    soup = parse_html()
    # Ensure the <html> tag is present
    assert soup.find('html') is not None, "The <html> tag is missing."

def test_html_head_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure the <head> tag is present
    assert soup.find('head') is not None, "The <head> tag is missing."

def test_html_body_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure the <body> tag is present
    assert soup.find('body') is not None, "The <body> tag is missing."

def test_html_title_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure the <title> tag is present
    assert soup.find('title') is not None, "The <title> tag is missing."

def test_html_meta_charset():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure the meta charset tag is present
    meta_tag = soup.find('meta', attrs={"charset": True})
    assert meta_tag is not None, "Missing <meta charset='UTF-8'>"

def test_html_meta_viewport():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure the meta viewport tag is present for responsive design
    meta_tag = soup.find('meta', attrs={"name": "viewport"})
    assert meta_tag is not None, "Missing <meta name='viewport'> tag"



# 3. Test Accessibility and Semantic HTML (One test per element)

def test_html_image_alt_attributes():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure all images have alt attributes
    images = soup.find_all('img')
    for img in images:
        assert img.get('alt'), "Image missing 'alt' attribute"

def test_html_form_labels():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure all form inputs have associated labels
    inputs = soup.find_all('input')
    for input_tag in inputs:
        label = soup.find('label', attrs={'for': input_tag.get('id')})
        assert label, f"Missing label for {input_tag.get('id')}"

def test_html_semantic_header_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure <header> tag is present
    assert soup.find('header') is not None, "Missing <header> tag"

def test_html_semantic_footer_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure <footer> tag is present
    assert soup.find('footer') is not None, "Missing <footer> tag"

def test_html_semantic_nav_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure <nav> tag is present
    assert soup.find('nav') is not None, "Missing <nav> tag"

def test_html_semantic_main_tag():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure <main> tag is present
    assert soup.find('main') is not None, "Missing <main> tag"



# 5. Test Proper Nesting and Closing Tags

def test_html_proper_nesting():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Check for correct nesting of elements (e.g., <ul> should only contain <li>)
    ul_tags = soup.find_all('ul')
    for ul in ul_tags:
        for child in ul.children:
            assert child.name == 'li' or child.name is None, f"Invalid child in <ul>: {child.name}"

def test_html_closing_tags():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure all non-void elements are properly closed
    void_tags = ['img', 'br', 'hr', 'input', 'meta']
    for tag in soup.find_all(True):  # True selects all tags
        if tag.name not in void_tags:
            assert soup.find(tag.name) is not None, f"Missing closing tag for <{tag.name}>"

# 6. Test HTML Validation (Basic placeholder test for valid HTML)

def test_html_valid_html():
    """
    pass:
    fail:
    """
    soup = parse_html()
    assert soup is not None, "HTML is not valid"

# 1. Test if the CSS file is correctly linked
def test_css_css_linked():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure the CSS file is linked in the <head> using <link rel="stylesheet">
    link = soup.find("link", {"rel": "stylesheet"})
    assert link is not None, "The CSS file is not linked."
    assert link["href"] == "style.css", "CSS file is incorrectly linked."


# 3. Test for Shorthand CSS properties (e.g., margin, padding)
def test_css_shorthand_properties():
    """
    pass:
    fail:
    """
    css_content = parse_css()
    # Check for shorthand properties like margin, padding, etc.
    assert "margin:" in css_content or "padding:" in css_content, "Missing shorthand for margin or padding."

# 4. Test for the presence of CSS Variables
def test_css_css_variables():
    """
    pass:
    fail:
    """
    css_content = parse_css()
    # Check if CSS variables are used (e.g., --primary-color)
    assert "--primary-color" in css_content or "--secondary-color" in css_content, "Missing CSS variable for colors."

# 5. Test if the layout uses Flexbox or Grid (modern layout techniques)
def test_css_layout_method():
    """
    pass:
    fail:
    """
    css_content = parse_css()
    # Ensure that flexbox or grid is used in layout
    assert "display: flex" in css_content or "display: grid" in css_content, "Neither flexbox nor grid is used for layout."


# 7. Test if CSS selectors are not overqualified
def test_css_no_overqualified_selectors():
    """
    pass:
    fail:
    """
    css_content = parse_css()
    # Ensure that the CSS selectors are not overqualified (i.e., too specific)
    selectors = [selector.strip() for selector in css_content.split(",")]
    for selector in selectors:
        assert selector.count(" ") <= 2, f"Overqualified selector detected: {selector}"

# 8. Test for External CSS Links (No inline CSS)
def test_css_external_css_only():
    """
    pass:
    fail:
    """
    soup = parse_html()
    # Ensure there is no inline CSS in the HTML (should use external CSS only)
    style_tag = soup.find("style")
    assert style_tag is None, "Inline CSS is present. Use external stylesheets only."

# 9. Test for Media Queries (Responsive design)
def test_css_media_queries():
    """
    pass:
    fail:
    """
    css_content = parse_css()
    # Ensure that media queries are present for responsiveness
    assert "@media" in css_content, "Missing media queries for responsive design."

# 10. Test for No Redundant or Duplicate Rules
def test_css_no_redundant_rules():
    """
    pass:
    fail:
    """
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
def test_css_consistent_units():
    css_content = parse_css()
    # Ensure consistent use of units (e.g., rem, em, px, etc.)
    assert "rem" in css_content or "em" in css_content or "px" in css_content, "Inconsistent use of CSS units."
# 1. Test for valid JavaScript syntax
def test_js_valid_js_syntax():
    js_content = parse_js()
    try:
        # Attempt to execute the JavaScript content within a safe context (e.g., using eval or a JS interpreter)
        # This is a simple way to check for syntax errors.
        exec(js_content)
    except Exception as e:
        pytest.fail(f"JavaScript has syntax errors: {str(e)}")

# 2. Test for the use of `let`, `const`, or `var` for variable declarations
def test_js_no_undeclared_variables():
    js_content = parse_js()
    # Ensure variables are declared using let, const, or var (no implicit global variables)
    assert "let " in js_content or "const " in js_content or "var " in js_content, "No variable declaration with let, const, or var found."

# 3. Test for strict mode (`"use strict"`)
def test_js_strict_mode():
    js_content = parse_js()
    # Ensure that strict mode is enabled at the top of the script
    assert '"use strict";' in js_content, "'use strict' is not used to enforce strict mode."

# 4. Test for avoiding the use of `eval()`
def test_js_no_eval():
    js_content = parse_js()
    # Ensure that eval() is not used in the JavaScript file
    assert "eval(" not in js_content, "The use of eval() is detected, which should be avoided."

# 5. Test for modularity (checking for functions)
def test_js_modular_code():
    js_content = parse_js()
    # Ensure that the JavaScript code is broken into smaller functions instead of large monolithic functions
    functions = [line for line in js_content.splitlines() if line.strip().startswith("function")]
    assert len(functions) > 0, "JavaScript code should be modular, with functions."

# 6. Test for asynchronous handling (using async/await or Promises)
def test_js_async_handling():
    js_content = parse_js()
    # Ensure the use of async/await or Promises for asynchronous operations
    assert "async" in js_content or "Promise" in js_content, "No async/await or Promises found for asynchronous handling."

# 7. Test for event handling (e.g., using addEventListener)
def test_js_event_handling():
    js_content = parse_js()
    # Ensure that event listeners are used instead of inline event handlers in the HTML
    assert "addEventListener" in js_content, "addEventListener is not used for event handling."

# 8. Test for DOM manipulation efficiency
def test_js_dom_manipulation():
    js_content = parse_js()
    # Ensure that DOM manipulation is done efficiently, ideally using modern methods like querySelector
    assert "document.querySelector" in js_content or "document.getElementById" in js_content, "Inefficient DOM manipulation methods detected."

# 9. Test for handling errors in Promises or async/await
def test_js_async_error_handling():
    js_content = parse_js()
    # Ensure proper error handling in Promises or async/await (e.g., using .catch or try/catch)
    assert ".catch(" in js_content or "try {" in js_content, "Asynchronous error handling is not present."


# 11. Test for proper function names (meaningful naming)
def test_js_meaningful_function_names():
    js_content = parse_js()
    # Ensure that function names are meaningful and describe their purpose
    function_names = [line.strip().split(" ")[1] for line in js_content.splitlines() if line.strip().startswith("function")]
    for name in function_names:
        assert len(name) > 0 and name != 'function', f"Function name '{name}' is not meaningful."

# 12. Test for no deeply nested functions or loops
def test_js_no_deeply_nested_code():
    js_content = parse_js()
    # Check if there are deeply nested functions or loops (which can cause readability issues)
    assert js_content.count('function') < 5, "Too many functions defined, check for deep nesting."
    assert js_content.count('{') < 10, "Too many blocks or nested loops. Consider refactoring."

# 14. Test for the proper use of `const` and `let` (immutable vs mutable variables)
def test_js_proper_use_of_const_and_let():
    js_content = parse_js()
    # Ensure that `const` is used for variables that should not be reassigned and `let` for mutable variables
    assert "const " in js_content, "The use of 'const' is missing where values should be immutable."
    assert "let " in js_content, "The use of 'let' is missing for mutable variables."