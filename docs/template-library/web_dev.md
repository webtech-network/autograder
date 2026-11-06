# Web Development Template (`webdev`)

The Web Development template provides test functions for validating HTML, CSS, and JavaScript files. It does **not** require a sandbox — all validation is performed through static analysis using BeautifulSoup and regex pattern matching.

Parameters, defaults, constraints and capabilities of every evaluator below are in the generated [evaluator reference](../reference/evaluators.md#webdev); this page explains what the checks mean.

> **Template name for configs:** `webdev`  
> **Requires sandbox:** No  
> **File types:** HTML, CSS, JavaScript

Each selected HTML file is parsed once per grading and the tree is shared by
every criterion over that file (`web_dev/documents.py`). The tree lives only as
long as the grading's submission file; nothing is cached across submissions.
Evaluators that read HTML call `parsed_html(file)` and must treat the result as
read-only.

---

## HTML Tests

### `has_tag`
Checks if a specific HTML tag appears a minimum number of times.

```json
{"id": "has-tag", "type": "has_tag", "name": "Has tag", "parameters": {"tag": "header", "required_count": 1}, "weight": 50}
```

---

### `has_class`
Checks for CSS classes in the HTML, with **wildcard support** (e.g., `col-*` matches `col-md-6`, `col-lg-4`, etc.).

```json
{"id": "has-class", "type": "has_class", "name": "Has class", "parameters": {"class_names": ["col-*", "container"], "required_count": 3}, "weight": 50}
```

---

### `has_attribute`
Checks if a specific HTML attribute is present on any tag a minimum number of times.

```json
{"id": "has-attribute", "type": "has_attribute", "name": "Has attribute", "parameters": {"attribute": "alt", "required_count": 3}, "weight": 30}
```

---

### `has_forbidden_tag`
Checks for a **forbidden** HTML tag and penalizes if found.

```json
{"id": "has-forbidden-tag", "type": "has_forbidden_tag", "name": "Has forbidden tag", "parameters": {"tag": "marquee"}, "weight": 100}
```

---

### `check_bootstrap_linked`
Verifies that the Bootstrap framework (CSS or JS) is linked in the HTML file.

```json
{"id": "check-bootstrap-linked", "type": "check_bootstrap_linked", "name": "Check bootstrap linked", "parameters": {}, "weight": 100}
```

---

### `check_bootstrap_usage`
**Penalty test** — checks if Bootstrap is being used. Scores 0 if found, 100 if not. Use in penalty categories to deduct points for using Bootstrap when it's not allowed.

---

### `check_internal_links`
Verifies that anchor links (`<a href="#id">`) point to valid element IDs within the document.

---

### `check_internal_links_to_article`
Verifies that anchor links point to IDs on `<article>` elements specifically.

---

### `check_no_unclosed_tags`
Detects HTML tags that were opened but not properly closed. Ignores void elements (`<br>`, `<img>`, etc.).

---

### `check_no_inline_styles`
Ensures no inline `style="..."` attributes are used in the HTML.

---

### `uses_semantic_tags`
Checks if the HTML uses at least one semantic tag (`<article>`, `<section>`, `<nav>`, `<aside>`, `<figure>`).

---

### `check_css_linked`
Verifies an external CSS stylesheet is linked via `<link rel="stylesheet">`.

---

### `check_headings_sequential`
Verifies heading levels (`<h1>` through `<h6>`) don't skip levels (e.g., `<h1>` → `<h3>` without `<h2>` is flagged).

---

### `check_all_images_have_alt`
Checks that all `<img>` tags have a non-empty `alt` attribute. Scores proportionally.

---

### `check_html_direct_children`
Ensures the only direct children of `<html>` are `<head>` and `<body>`.

---

### `check_tag_not_inside`
Verifies a specific tag is NOT nested inside another specific tag.

```json
{"id": "check-tag-not-inside", "type": "check_tag_not_inside", "name": "Check tag not inside", "parameters": {"child_tag": "div", "parent_tag": "span"}, "weight": 50}
```

---

### `check_head_details`
Verifies a specific tag exists inside the `<head>` section.

---

### `check_attribute_and_value`
Checks if a tag has a specific attribute with a specific value.

```json
{"id": "check-attribute-and-value", "type": "check_attribute_and_value", "name": "Check attribute and value", "parameters": {"tag": "html", "attribute": "lang", "value": "pt-BR"}, "weight": 30}
```

---

### `link_points_to_page_with_query_param`
Checks for anchor tags linking to a specific page with a required query string parameter.

---

## CSS Tests

### `css_uses_property`
Checks if a specific CSS property-value pair exists in the stylesheet.

```json
{"id": "css-uses-property", "type": "css_uses_property", "name": "Css uses property", "parameters": {"prop": "display", "value": "flex"}, "weight": 50}
```

---

### `has_style`
Checks if a CSS style rule appears a minimum number of times.

---

### `count_over_usage`
**Penalty test** — penalizes if a specific text string appears more than a maximum number of times in CSS.

---

### `check_id_selector_over_usage`
**Penalty test** — counts CSS ID selectors (`#id`) and penalizes if they exceed a maximum.

---

### `uses_relative_units`
Checks if the CSS uses relative units (`em`, `rem`, `%`, `vh`, `vw`).

---

### `check_media_queries`
Checks if the CSS contains `@media` queries for responsive design.

---

### `check_flexbox_usage`
Checks if Flexbox properties (`display: flex` or `flex-*`) are used.

---

## JavaScript Tests

### `js_uses_feature`
Performs a simple string search to check if a JavaScript feature/keyword is present.

```json
{"id": "js-uses-feature", "type": "js_uses_feature", "name": "Js uses feature", "parameters": {"feature": "addEventListener"}, "weight": 50}
```

---

### `uses_forbidden_method`
**Penalty test** — checks for a forbidden JavaScript method and penalizes if found.

---

### `count_global_vars`
**Penalty test** — counts top-level `var`/`let`/`const` declarations and penalizes if too many.

---

### `js_uses_query_string_parsing`
Checks if the JS code uses URL query string parsing (`URLSearchParams` or `window.location.search`).

---

### `js_has_json_array_with_id`
Checks for a JS array of objects where each object has a specific required key.

---

### `js_uses_dom_manipulation`
Checks for DOM manipulation method calls in the JavaScript code.

```json
{"id": "js-uses-dom-manipulation", "type": "js_uses_dom_manipulation", "name": "Js uses dom manipulation", "parameters": {"methods": ["createElement", "appendChild", "textContent"], "required_count": 5}, "weight": 60}
```

---

### `has_no_js_framework`
**Penalty test** — detects forbidden JS frameworks (React, Vue, Angular) across HTML and JS files.

---

## Project Structure Tests

### `check_dir_exists`
Checks if a directory exists in the submission by looking for files with that path prefix.

---

### `check_project_structure`
Checks if a specific file path exists in the submission.

---

### `count_unused_css_classes`
Finds CSS classes defined in the stylesheet but not used in HTML, or vice versa.

---

## Usage Example

A complete, schema-checked definition using this template is [`docs/contracts/v1/examples/webdev.json`](../contracts/v1/examples/webdev.json). Bonus and penalty weights are nonnegative caps, and either category may contain subjects as well as tests. Over HTTP, send the definition as `definition` in the configuration envelope (`POST /api/v1/configs`, see [API.md](../API.md)). A snippet above is one criterion; [DEFINITIONS.md](../contracts/DEFINITIONS.md) describes the whole object.

