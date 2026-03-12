# Web Development Template (`web_dev`)

The Web Development template provides test functions for validating HTML, CSS, and JavaScript files. It does **not** require a sandbox — all validation is performed through static analysis using BeautifulSoup and regex pattern matching.

> **Template name for configs:** `web_dev`  
> **Requires sandbox:** No  
> **File types:** HTML, CSS, JavaScript

---

## HTML Tests

### `has_tag`
Checks if a specific HTML tag appears a minimum number of times.

| Parameter | Type | Description |
|-----------|------|-------------|
| `tag` | string | The HTML tag to search for (e.g., `"div"`, `"header"`) |
| `required_count` | integer | Minimum number of occurrences required |

```json
{ "name": "has_tag", "parameters": { "tag": "header", "required_count": 1 }, "weight": 50 }
```

---

### `has_class`
Checks for CSS classes in the HTML, with **wildcard support** (e.g., `col-*` matches `col-md-6`, `col-lg-4`, etc.).

| Parameter | Type | Description |
|-----------|------|-------------|
| `class_names` | list[string] | Class names to search for. Wildcards (`*`) supported. |
| `required_count` | integer | Minimum total number of matching class occurrences |

```json
{ "name": "has_class", "parameters": { "class_names": ["col-*", "container"], "required_count": 3 }, "weight": 50 }
```

---

### `has_attribute`
Checks if a specific HTML attribute is present on any tag a minimum number of times.

| Parameter | Type | Description |
|-----------|------|-------------|
| `attribute` | string | The attribute to search for (e.g., `"alt"`, `"href"`) |
| `required_count` | integer | Minimum number of occurrences required |

```json
{ "name": "has_attribute", "parameters": { "attribute": "alt", "required_count": 3 }, "weight": 30 }
```

---

### `has_forbidden_tag`
Checks for a **forbidden** HTML tag and penalizes if found.

| Parameter | Type | Description |
|-----------|------|-------------|
| `tag` | string | The forbidden tag (e.g., `"marquee"`, `"blink"`) |

```json
{ "name": "has_forbidden_tag", "parameters": { "tag": "marquee" }, "weight": 100 }
```

---

### `check_bootstrap_linked`
Verifies that the Bootstrap framework (CSS or JS) is linked in the HTML file.

*No parameters.*

```json
{ "name": "check_bootstrap_linked", "parameters": {}, "weight": 100 }
```

---

### `check_bootstrap_usage`
**Penalty test** — checks if Bootstrap is being used. Scores 0 if found, 100 if not. Use in penalty categories to deduct points for using Bootstrap when it's not allowed.

*No parameters.*

---

### `check_internal_links`
Verifies that anchor links (`<a href="#id">`) point to valid element IDs within the document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `required_count` | integer | Minimum number of valid internal links |

---

### `check_internal_links_to_article`
Verifies that anchor links point to IDs on `<article>` elements specifically.

| Parameter | Type | Description |
|-----------|------|-------------|
| `required_count` | integer | Minimum number of valid links to `<article>` elements |

---

### `check_no_unclosed_tags`
Detects HTML tags that were opened but not properly closed. Ignores void elements (`<br>`, `<img>`, etc.).

*No parameters.*

---

### `check_no_inline_styles`
Ensures no inline `style="..."` attributes are used in the HTML.

*No parameters.*

---

### `uses_semantic_tags`
Checks if the HTML uses at least one semantic tag (`<article>`, `<section>`, `<nav>`, `<aside>`, `<figure>`).

*No parameters.*

---

### `check_css_linked`
Verifies an external CSS stylesheet is linked via `<link rel="stylesheet">`.

*No parameters.*

---

### `check_headings_sequential`
Verifies heading levels (`<h1>` through `<h6>`) don't skip levels (e.g., `<h1>` → `<h3>` without `<h2>` is flagged).

*No parameters.*

---

### `check_all_images_have_alt`
Checks that all `<img>` tags have a non-empty `alt` attribute. Scores proportionally.

*No parameters.*

---

### `check_html_direct_children`
Ensures the only direct children of `<html>` are `<head>` and `<body>`.

*No parameters.*

---

### `check_tag_not_inside`
Verifies a specific tag is NOT nested inside another specific tag.

| Parameter | Type | Description |
|-----------|------|-------------|
| `child_tag` | string | The tag that should not be nested |
| `parent_tag` | string | The parent tag to check inside |

```json
{ "name": "check_tag_not_inside", "parameters": { "child_tag": "div", "parent_tag": "span" }, "weight": 50 }
```

---

### `check_head_details`
Verifies a specific tag exists inside the `<head>` section.

| Parameter | Type | Description |
|-----------|------|-------------|
| `detail_tag` | string | Tag to look for (e.g., `"title"`, `"meta"`) |

---

### `check_attribute_and_value`
Checks if a tag has a specific attribute with a specific value.

| Parameter | Type | Description |
|-----------|------|-------------|
| `tag` | string | The HTML tag |
| `attribute` | string | The attribute name |
| `value` | string | The expected attribute value |

```json
{ "name": "check_attribute_and_value", "parameters": { "tag": "html", "attribute": "lang", "value": "pt-BR" }, "weight": 30 }
```

---

### `link_points_to_page_with_query_param`
Checks for anchor tags linking to a specific page with a required query string parameter.

| Parameter | Type | Description |
|-----------|------|-------------|
| `target_page` | string | Expected page (e.g., `"details.html"`) |
| `query_param` | string | Required query parameter name (e.g., `"id"`) |
| `required_count` | integer | Minimum number of valid links |

---

## CSS Tests

### `css_uses_property`
Checks if a specific CSS property-value pair exists in the stylesheet.

| Parameter | Type | Description |
|-----------|------|-------------|
| `prop` | string | CSS property (e.g., `"display"`) |
| `value` | string | Expected value (e.g., `"flex"`) |

```json
{ "name": "css_uses_property", "parameters": { "prop": "display", "value": "flex" }, "weight": 50 }
```

---

### `has_style`
Checks if a CSS style rule appears a minimum number of times.

| Parameter | Type | Description |
|-----------|------|-------------|
| `style` | string | The CSS property to count (e.g., `"margin"`) |
| `count` | integer | Minimum number of occurrences |

---

### `count_over_usage`
**Penalty test** — penalizes if a specific text string appears more than a maximum number of times in CSS.

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | string | The text to count |
| `max_allowed` | integer | Maximum allowed occurrences |

---

### `check_id_selector_over_usage`
**Penalty test** — counts CSS ID selectors (`#id`) and penalizes if they exceed a maximum.

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_allowed` | integer | Maximum number of ID selectors allowed |

---

### `uses_relative_units`
Checks if the CSS uses relative units (`em`, `rem`, `%`, `vh`, `vw`).

*No parameters.*

---

### `check_media_queries`
Checks if the CSS contains `@media` queries for responsive design.

*No parameters.*

---

### `check_flexbox_usage`
Checks if Flexbox properties (`display: flex` or `flex-*`) are used.

*No parameters.*

---

## JavaScript Tests

### `js_uses_feature`
Performs a simple string search to check if a JavaScript feature/keyword is present.

| Parameter | Type | Description |
|-----------|------|-------------|
| `feature` | string | The string to search for (e.g., `"addEventListener"`) |

```json
{ "name": "js_uses_feature", "parameters": { "feature": "addEventListener" }, "weight": 50 }
```

---

### `uses_forbidden_method`
**Penalty test** — checks for a forbidden JavaScript method and penalizes if found.

| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | string | The forbidden method name (e.g., `"alert"`) |

---

### `count_global_vars`
**Penalty test** — counts top-level `var`/`let`/`const` declarations and penalizes if too many.

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_allowed` | integer | Maximum global variables allowed |

---

### `js_uses_query_string_parsing`
Checks if the JS code uses URL query string parsing (`URLSearchParams` or `window.location.search`).

*No parameters.*

---

### `js_has_json_array_with_id`
Checks for a JS array of objects where each object has a specific required key.

| Parameter | Type | Description |
|-----------|------|-------------|
| `required_key` | string | Key that must exist in each object (e.g., `"id"`) |
| `min_items` | integer | Minimum number of items expected |

---

### `js_uses_dom_manipulation`
Checks for DOM manipulation method calls in the JavaScript code.

| Parameter | Type | Description |
|-----------|------|-------------|
| `methods` | list[string] | Methods to search for (e.g., `["createElement", "appendChild"]`) |
| `required_count` | integer | Minimum total occurrences |

```json
{ "name": "js_uses_dom_manipulation", "parameters": { "methods": ["createElement", "appendChild", "textContent"], "required_count": 5 }, "weight": 60 }
```

---

### `has_no_js_framework`
**Penalty test** — detects forbidden JS frameworks (React, Vue, Angular) across HTML and JS files.

| Parameter | Type | Description |
|-----------|------|-------------|
| `html_file` | string | HTML file to check (e.g., `"index.html"`) |
| `js_file` | string | JS file to check (e.g., `"script.js"`) |

---

## Project Structure Tests

### `check_dir_exists`
Checks if a directory exists in the submission by looking for files with that path prefix.

| Parameter | Type | Description |
|-----------|------|-------------|
| `dir_path` | string | Directory path to check (e.g., `"css/"`) |

---

### `check_project_structure`
Checks if a specific file path exists in the submission.

| Parameter | Type | Description |
|-----------|------|-------------|
| `expected_structure` | string | Expected file path (e.g., `"css/styles.css"`) |

---

### `Count Unused Css Classes`
Finds CSS classes defined in the stylesheet but not used in HTML, or vice versa.

| Parameter | Type | Description |
|-----------|------|-------------|
| `html_file` | string | HTML filename (e.g., `"index.html"`) |
| `css_file` | string | CSS filename (e.g., `"styles.css"`) |

---

## Usage Example

```json
{
  "external_assignment_id": "web-portfolio",
  "template_name": "web_dev",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "HTML Structure",
          "weight": 40,
          "tests": [
            { "name": "has_tag", "parameters": { "tag": "header", "required_count": 1 }, "weight": 30 },
            { "name": "has_tag", "parameters": { "tag": "nav", "required_count": 1 }, "weight": 20 },
            { "name": "uses_semantic_tags", "parameters": {}, "weight": 20 },
            { "name": "check_all_images_have_alt", "parameters": {}, "weight": 30 }
          ]
        },
        {
          "subject_name": "CSS Styling",
          "weight": 35,
          "tests": [
            { "name": "check_css_linked", "parameters": {}, "weight": 20 },
            { "name": "check_flexbox_usage", "parameters": {}, "weight": 30 },
            { "name": "check_media_queries", "parameters": {}, "weight": 30 },
            { "name": "uses_relative_units", "parameters": {}, "weight": 20 }
          ]
        },
        {
          "subject_name": "JavaScript",
          "weight": 25,
          "tests": [
            { "name": "js_uses_feature", "parameters": { "feature": "addEventListener" }, "weight": 50 },
            { "name": "js_uses_dom_manipulation", "parameters": { "methods": ["createElement", "appendChild"], "required_count": 3 }, "weight": 50 }
          ]
        }
      ]
    },
    "penalty": {
      "weight": -20,
      "tests": [
        { "name": "check_no_inline_styles", "parameters": {}, "weight": 50 },
        { "name": "has_no_js_framework", "parameters": { "html_file": "index.html", "js_file": "script.js" }, "weight": 50 }
      ]
    }
  }
}
```

