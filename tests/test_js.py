import pytest

# Helper function to read the JavaScript file
def parse_js():
    with open('../submission/script.js', 'r') as file:
        return file.read()

# 1. Test for valid JavaScript syntax
def test_valid_js_syntax():
    js_content = parse_js()
    try:
        # Attempt to execute the JavaScript content within a safe context (e.g., using eval or a JS interpreter)
        # This is a simple way to check for syntax errors.
        exec(js_content)
    except Exception as e:
        pytest.fail(f"JavaScript has syntax errors: {str(e)}")

# 2. Test for the use of `let`, `const`, or `var` for variable declarations
def test_no_undeclared_variables():
    js_content = parse_js()
    # Ensure variables are declared using let, const, or var (no implicit global variables)
    assert "let " in js_content or "const " in js_content or "var " in js_content, "No variable declaration with let, const, or var found."

# 3. Test for strict mode (`"use strict"`)
def test_strict_mode():
    js_content = parse_js()
    # Ensure that strict mode is enabled at the top of the script
    assert '"use strict";' in js_content, "'use strict' is not used to enforce strict mode."

# 4. Test for avoiding the use of `eval()`
def test_no_eval():
    js_content = parse_js()
    # Ensure that eval() is not used in the JavaScript file
    assert "eval(" not in js_content, "The use of eval() is detected, which should be avoided."

# 5. Test for modularity (checking for functions)
def test_modular_code():
    js_content = parse_js()
    # Ensure that the JavaScript code is broken into smaller functions instead of large monolithic functions
    functions = [line for line in js_content.splitlines() if line.strip().startswith("function")]
    assert len(functions) > 0, "JavaScript code should be modular, with functions."

# 6. Test for asynchronous handling (using async/await or Promises)
def test_async_handling():
    js_content = parse_js()
    # Ensure the use of async/await or Promises for asynchronous operations
    assert "async" in js_content or "Promise" in js_content, "No async/await or Promises found for asynchronous handling."

# 7. Test for event handling (e.g., using addEventListener)
def test_event_handling():
    js_content = parse_js()
    # Ensure that event listeners are used instead of inline event handlers in the HTML
    assert "addEventListener" in js_content, "addEventListener is not used for event handling."

# 8. Test for DOM manipulation efficiency
def test_dom_manipulation():
    js_content = parse_js()
    # Ensure that DOM manipulation is done efficiently, ideally using modern methods like querySelector
    assert "document.querySelector" in js_content or "document.getElementById" in js_content, "Inefficient DOM manipulation methods detected."

# 9. Test for handling errors in Promises or async/await
def test_async_error_handling():
    js_content = parse_js()
    # Ensure proper error handling in Promises or async/await (e.g., using .catch or try/catch)
    assert ".catch(" in js_content or "try {" in js_content, "Asynchronous error handling is not present."

# 10. Test for preventing memory leaks
def test_memory_leaks():
    js_content = parse_js()
    # Ensure that event listeners or intervals are properly cleaned up to avoid memory leaks
    assert ".removeEventListener" in js_content or "clearInterval" in js_content or "clearTimeout" in js_content, "Memory leaks may occur due to unremoved event listeners or intervals."

# 11. Test for proper function names (meaningful naming)
def test_meaningful_function_names():
    js_content = parse_js()
    # Ensure that function names are meaningful and describe their purpose
    function_names = [line.strip().split(" ")[1] for line in js_content.splitlines() if line.strip().startswith("function")]
    for name in function_names:
        assert len(name) > 0 and name != 'function', f"Function name '{name}' is not meaningful."

# 12. Test for no deeply nested functions or loops
def test_no_deeply_nested_code():
    js_content = parse_js()
    # Check if there are deeply nested functions or loops (which can cause readability issues)
    assert js_content.count('function') < 5, "Too many functions defined, check for deep nesting."
    assert js_content.count('{') < 10, "Too many blocks or nested loops. Consider refactoring."

# 13. Test for proper use of array methods (e.g., map, filter, reduce)
def test_array_methods():
    js_content = parse_js()
    # Ensure that array methods like map, filter, reduce are used instead of traditional loops
    assert "map(" in js_content or "filter(" in js_content or "reduce(" in js_content, "Array methods like map, filter, or reduce are not used."

# 14. Test for the proper use of `const` and `let` (immutable vs mutable variables)
def test_proper_use_of_const_and_let():
    js_content = parse_js()
    # Ensure that `const` is used for variables that should not be reassigned and `let` for mutable variables
    assert "const " in js_content, "The use of 'const' is missing where values should be immutable."
    assert "let " in js_content, "The use of 'let' is missing for mutable variables."
