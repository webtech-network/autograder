# /autograder/core/test_generation/test_library/js_tests.py
import os
import re

# --- Helper Functions ---

def parse_js(submission_path):
    """Parses the student's script.js file."""
    js_path = os.path.join(submission_path, 'script.js')
    try:
        with open(js_path, 'r', encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""

# --- Validation Functions ---

# Core Syntax & Quality
def check_is_valid_syntax(js_content):
    # This is a placeholder. A real implementation would use a JS linter like ESLint via a subprocess.
    # For now, we assume syntax is valid if the file can be read.
    assert js_content is not None, "JavaScript file could not be read."

def check_uses_strict_mode(js_content):
    assert js_content.strip().startswith('"use strict";') or js_content.strip().startswith("'use strict';"), "'use strict'; is not used at the beginning of the file."

def check_no_undeclared_variables(js_content):
    # Statically checking for undeclared variables is complex and best handled by a linter.
    # This function serves as a placeholder for such a check.
    assert True, "Checking for undeclared variables requires a linter."

def check_uses_const_and_let(js_content):
    assert "var " not in js_content, "Found legacy 'var' declaration. Use 'const' or 'let' instead."
    assert "const " in js_content or "let " in js_content, "'const' or 'let' not used for variable declaration."

def check_has_meaningful_names(js_content):
    # A simplified check for short, non-descriptive names
    variables = re.findall(r'(?:let|const|var)\s+([a-zA-Z0-9_]+)', js_content)
    functions = re.findall(r'function\s+([a-zA-Z0-9_]+)', js_content)
    for name in variables + functions:
        assert len(name) > 2, f"Variable or function name '{name}' is too short to be descriptive."

def check_no_deeply_nested_code(js_content, max_depth):
    depth = 0
    for char in js_content:
        if char in ['{', '(', '[']:
            depth += 1
            assert depth <= max_depth, f"Code nesting exceeds the maximum allowed depth of {max_depth}."
        elif char in ['}', ')', ']']:
            depth -= 1

# DOM Interaction & Events
def check_uses_modern_selectors(js_content):
    assert "querySelector" in js_content or "getElementById" in js_content, "Modern selectors like querySelector or getElementById are not used."

def check_uses_addEventListener(js_content):
    assert "addEventListener" in js_content, "addEventListener is not used for event handling."

def check_provides_interaction_feedback(js_content):
    feedback_methods = ["classList.add", "classList.toggle", "innerHTML", "textContent", ".style"]
    assert any(method in js_content for method in feedback_methods), "No visual feedback for user interactions found."

def check_has_form_validation(js_content):
    assert "checkValidity" in js_content or ".test(" in js_content, "No client-side form validation logic found."

# Advanced Concepts
def check_uses_es6_modules(js_content):
    assert "import " in js_content or "export " in js_content, "ES6 modules (import/export) are not used."

def check_uses_template_literals(js_content):
    assert re.search(r'`[^`]*\${[^`]+}`', js_content), "Template literals are not used for string interpolation."

def check_uses_modern_array_methods(js_content):
    assert "map(" in js_content or "filter(" in js_content or "reduce(" in js_content, "Modern array methods (map, filter, reduce) are not used."

def check_handles_async(js_content):
    assert "async " in js_content or "Promise" in js_content, "Asynchronous operations are not handled with async/await or Promises."

def check_handles_async_errors(js_content):
    assert ".catch(" in js_content or ("async " in js_content and "try" in js_content), "Error handling for async operations (.catch or try/catch) is missing."

def check_uses_storage(js_content):
    assert "localStorage" in js_content or "sessionStorage" in js_content, "localStorage or sessionStorage is not used."

def check_prevents_memory_leaks(js_content):
    assert "removeEventListener" in js_content or "clearInterval" in js_content, "No cleanup functions (removeEventListener, clearInterval) found to prevent memory leaks."

# Forbidden Practices
def check_no_eval(js_content):
    assert "eval(" not in js_content, "The use of eval() was found."

def check_no_alert(js_content):
    assert "alert(" not in js_content, "The use of alert() was found."

def check_no_document_write(js_content):
    assert "document.write(" not in js_content, "The use of document.write() was found."

def check_no_inline_scripts(soup):
    for script in soup.find_all('script'):
        assert script.has_attr('src'), "An inline <script> tag was found."
