# Web Development Template

**Registry key:** `webdev` · **Sandbox:** Not required · **Analysis:** Static (BeautifulSoup + regex)

The web development template tests static HTML, CSS, and JavaScript projects without executing any code. It parses submitted files and checks for structure, styling, scripting patterns, and project organization.

## Available Tests

### HTML Tests (19)

| Test Name | Purpose | Type |
|-----------|---------|------|
| [`has_tag`](#has_tag) | Check for HTML tags | Proportional |
| [`has_forbidden_tag`](#has_forbidden_tag) | Detect forbidden HTML tags | Penalty |
| [`has_attribute`](#has_attribute) | Check for HTML attributes | Proportional |
| [`check_attribute_and_value`](#check_attribute_and_value) | Check tag has specific attribute value | Binary |
| [`has_class`](#has_class) | Check for CSS classes in HTML (supports wildcards) | Proportional |
| [`check_bootstrap_linked`](#check_bootstrap_linked) | Verify Bootstrap is linked | Binary |
| [`check_bootstrap_usage`](#check_bootstrap_usage) | Detect Bootstrap usage (penalty) | Penalty |
| [`check_internal_links`](#check_internal_links) | Validate internal anchor links | Proportional |
| [`check_internal_links_to_article`](#check_internal_links_to_article) | Validate internal links pointing to articles | Proportional |
| [`link_points_to_page_with_query_param`](#link_points_to_page_with_query_param) | Check links with query parameters | Proportional |
| [`check_no_unclosed_tags`](#check_no_unclosed_tags) | Detect unclosed HTML tags | Binary |
| [`check_no_inline_styles`](#check_no_inline_styles) | Detect inline style attributes | Penalty |
| [`uses_semantic_tags`](#uses_semantic_tags) | Check for semantic HTML5 tags | Partial credit |
| [`check_css_linked`](#check_css_linked) | Verify external CSS is linked | Binary |
| [`check_head_details`](#check_head_details) | Check for specific tags in `<head>` | Binary |
| [`check_tag_not_inside`](#check_tag_not_inside) | Verify a tag is NOT inside another | Penalty |
| [`check_headings_sequential`](#check_headings_sequential) | Validate heading hierarchy (h1→h2→h3) | Binary |
| [`check_all_images_have_alt`](#check_all_images_have_alt) | Check all images have alt text | Proportional |
| [`check_html_direct_children`](#check_html_direct_children) | Verify `<html>` has only `<head>` and `<body>` | Binary |

### CSS Tests (8)

| Test Name | Purpose | Type |
|-----------|---------|------|
| [`css_uses_property`](#css_uses_property) | Check for a CSS property-value pair | Binary |
| [`has_style`](#has_style) | Count occurrences of a CSS property | Proportional |
| [`count_over_usage`](#count_over_usage) | Limit usage of a CSS pattern | Penalty |
| [`check_id_selector_over_usage`](#check_id_selector_over_usage) | Limit `#id` selectors | Penalty |
| [`uses_relative_units`](#uses_relative_units) | Check for relative CSS units | Binary |
| [`check_media_queries`](#check_media_queries) | Check for `@media` rules | Binary |
| [`check_flexbox_usage`](#check_flexbox_usage) | Check for flexbox usage | Binary |
| [`count_unused_css_classes`](#count_unused_css_classes) | Detect CSS classes not used in HTML | Binary |

### JavaScript Tests (7)

| Test Name | Purpose | Type |
|-----------|---------|------|
| [`js_uses_feature`](#js_uses_feature) | Check for a JS feature/keyword | Binary |
| [`uses_forbidden_method`](#uses_forbidden_method) | Detect forbidden JS methods | Penalty |
| [`count_global_vars`](#count_global_vars) | Limit global variable declarations | Penalty |
| [`js_uses_query_string_parsing`](#js_uses_query_string_parsing) | Check for URL query string parsing | Binary |
| [`js_has_json_array_with_id`](#js_has_json_array_with_id) | Check for JSON array with required keys | Proportional |
| [`js_uses_dom_manipulation`](#js_uses_dom_manipulation) | Check for DOM manipulation methods | Proportional |
| [`has_no_js_framework`](#has_no_js_framework) | Detect JS framework usage (penalty) | Penalty |

### Structure Tests (2)

| Test Name | Purpose | Type |
|-----------|---------|------|
| [`check_project_structure`](#check_project_structure) | Verify a file exists in submission | Binary |
| [`check_dir_exists`](#check_dir_exists) | Verify a directory exists in submission | Binary |

---

## Scoring Types

- **Binary**: 100 (pass) or 0 (fail)
- **Proportional**: `min(100, found / required × 100)` — partial credit based on how many items were found
- **Penalty**: 0 when the forbidden item IS found, 100 when NOT found (use in `penalty` category)
- **Partial credit**: Special scoring (e.g., `uses_semantic_tags` gives 40 instead of 0)

---

## HTML Tests

### has_tag

Checks that a specific HTML tag appears at least `required_count` times.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tag` | string | `""` | HTML tag name (e.g., `"header"`, `"nav"`, `"article"`) |
| `required_count` | integer | `0` | Minimum number of occurrences. If `0`, score is always 100. |

**Scoring:** `min(100, found_count / required_count × 100)`

```json
{
  "name": "has_tag",
  "file": "index.html",
  "parameters": [
    { "name": "tag", "value": "section" },
    { "name": "required_count", "value": 3 }
  ]
}
```

---

### has_forbidden_tag

Checks that a specific HTML tag does **not** appear. Use in a `penalty` category.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tag` | string | `""` | HTML tag name to forbid |

**Scoring:** 0 if tag found, 100 if not found

```json
{
  "name": "has_forbidden_tag",
  "file": "index.html",
  "parameters": [
    { "name": "tag", "value": "marquee" }
  ]
}
```

---

### has_attribute

Checks that a specific HTML attribute appears at least `required_count` times across all elements.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `attribute` | string | `""` | Attribute name (e.g., `"alt"`, `"aria-label"`) |
| `required_count` | integer | `0` | Minimum occurrences. If `0`, score is always 100. |

**Scoring:** `min(100, found_count / required_count × 100)`

```json
{
  "name": "has_attribute",
  "file": "index.html",
  "parameters": [
    { "name": "attribute", "value": "alt" },
    { "name": "required_count", "value": 5 }
  ]
}
```

---

### check_attribute_and_value

Checks that at least one element matches a specific tag, attribute, and value combination.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tag` | string | `""` | HTML tag name |
| `attribute` | string | `""` | Attribute name |
| `value` | string | `""` | Expected attribute value |

**Scoring:** 100 if match found, 0 otherwise

```json
{
  "name": "check_attribute_and_value",
  "file": "index.html",
  "parameters": [
    { "name": "tag", "value": "meta" },
    { "name": "attribute", "value": "charset" },
    { "name": "value", "value": "UTF-8" }
  ]
}
```

---

### has_class

Checks that specific CSS class names appear in the HTML at least `required_count` times. Supports wildcard patterns with `*`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `class_names` | list of strings | `[]` | Class names to search for. Use `*` as wildcard (e.g., `"col-*"`) |
| `required_count` | integer | `0` | Minimum occurrences. If `0`, score is always 100. |

**Scoring:** `min(100, found_count / required_count × 100)`

!!! tip "Wildcard support"
    `"col-*"` matches `col-md-6`, `col-lg-4`, `col-12`, etc. The `*` is converted to a `\S*` regex pattern.

```json
{
  "name": "has_class",
  "file": "index.html",
  "parameters": [
    { "name": "class_names", "value": ["col-*"] },
    { "name": "required_count", "value": 6 }
  ]
}
```

---

### check_bootstrap_linked

Checks that Bootstrap CSS or JS is linked in the HTML.

**Parameters:** None

**Scoring:** 100 if a `<link>` or `<script>` referencing "bootstrap" is found (case-insensitive), 0 otherwise

```json
{
  "name": "check_bootstrap_linked",
  "file": "index.html"
}
```

---

### check_bootstrap_usage

Checks that Bootstrap is **not** linked. This is the inverse of `check_bootstrap_linked` — use it as a penalty when students should write their own CSS.

**Parameters:** None

**Scoring:** 0 if Bootstrap is linked (penalty), 100 if not found

```json
{
  "name": "check_bootstrap_usage",
  "file": "index.html"
}
```

---

### check_internal_links

Counts valid internal anchor links (`<a href="#id">`) where the target `id` actually exists in the document.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `required_count` | integer | `0` | Minimum valid internal links. If `0`, score is always 100. |

**Scoring:** `min(100, valid_links / required_count × 100)`

```json
{
  "name": "check_internal_links",
  "file": "index.html",
  "parameters": [
    { "name": "required_count", "value": 3 }
  ]
}
```

---

### check_internal_links_to_article

Same as `check_internal_links`, but the target element must be an `<article>` tag.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `required_count` | integer | `0` | Minimum valid links to articles |

**Scoring:** `min(100, valid_links / required_count × 100)`

```json
{
  "name": "check_internal_links_to_article",
  "file": "index.html",
  "parameters": [
    { "name": "required_count", "value": 3 }
  ]
}
```

---

### link_points_to_page_with_query_param

Counts `<a>` links whose `href` points to a specific page and includes a specific query parameter.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_page` | string | `""` | Target page path (e.g., `"details.html"`) |
| `query_param` | string | `""` | Required query parameter name (e.g., `"id"`) |
| `required_count` | integer | `0` | Minimum matching links |

**Scoring:** `min(100, matching_links / required_count × 100)`

```json
{
  "name": "link_points_to_page_with_query_param",
  "file": "index.html",
  "parameters": [
    { "name": "target_page", "value": "details.html" },
    { "name": "query_param", "value": "id" },
    { "name": "required_count", "value": 3 }
  ]
}
```

---

### check_no_unclosed_tags

Checks that all HTML tags are properly closed. Void elements (`br`, `img`, `input`, `hr`, `meta`, `link`, etc.) and structural tags (`html`, `head`, `body`) are excluded.

**Parameters:** None

**Scoring:** 100 if no unclosed tags, 0 if any unclosed tags found

```json
{
  "name": "check_no_unclosed_tags",
  "file": "index.html"
}
```

---

### check_no_inline_styles

Checks that no element has a `style` attribute. Use as a penalty to enforce external CSS.

**Parameters:** None

**Scoring:** 0 if any inline styles found, 100 if none

```json
{
  "name": "check_no_inline_styles",
  "file": "index.html"
}
```

---

### uses_semantic_tags

Checks for the presence of HTML5 semantic tags: `article`, `section`, `nav`, `aside`, `figure`.

**Parameters:** None

**Scoring:** 100 if any semantic tag found, **40** if none found (partial credit, not 0)

```json
{
  "name": "uses_semantic_tags",
  "file": "index.html"
}
```

!!! note "Partial credit"
    This is the only test that gives partial credit (40) instead of 0 on failure. This encourages semantic HTML without heavily penalizing students who use `<div>` layouts.

---

### check_css_linked

Checks that an external CSS stylesheet is linked via `<link rel="stylesheet">`.

**Parameters:** None

**Scoring:** 100 if found, 0 otherwise

```json
{
  "name": "check_css_linked",
  "file": "index.html"
}
```

---

### check_head_details

Checks that the `<head>` section contains a specific tag.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detail_tag` | string | `""` | Tag name to look for inside `<head>` (e.g., `"title"`, `"meta"`) |

**Scoring:** 100 if the tag exists inside `<head>`, 0 otherwise

```json
{
  "name": "check_head_details",
  "file": "index.html",
  "parameters": [
    { "name": "detail_tag", "value": "title" }
  ]
}
```

---

### check_tag_not_inside

Checks that a specific tag does **not** appear inside another tag. Use as a penalty.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `child_tag` | string | `""` | Tag that should NOT be nested |
| `parent_tag` | string | `""` | Parent tag to check inside |

**Scoring:** 0 if `child_tag` is found inside `parent_tag`, 100 if not

```json
{
  "name": "check_tag_not_inside",
  "file": "index.html",
  "parameters": [
    { "name": "child_tag", "value": "div" },
    { "name": "parent_tag", "value": "span" }
  ]
}
```

---

### check_headings_sequential

Checks that heading levels (h1–h6) follow a sequential order without skipping levels (e.g., h1→h3 is invalid, h1→h2→h3 is valid).

**Parameters:** None

**Scoring:** 100 if headings are sequential (or fewer than 2 headings), 0 if any level is skipped

```json
{
  "name": "check_headings_sequential",
  "file": "index.html"
}
```

---

### check_all_images_have_alt

Checks that every `<img>` tag has a non-empty `alt` attribute.

**Parameters:** None

**Scoring:** `images_with_alt / total_images × 100` (100 if no images exist)

```json
{
  "name": "check_all_images_have_alt",
  "file": "index.html"
}
```

---

### check_html_direct_children

Checks that `<html>` has exactly two direct children: `<head>` and `<body>`, with no other elements.

**Parameters:** None

**Scoring:** 100 if valid, 0 otherwise

```json
{
  "name": "check_html_direct_children",
  "file": "index.html"
}
```

---

## CSS Tests

### css_uses_property

Checks that a CSS property with a specific value exists in the stylesheet.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prop` | string | `""` | CSS property name (e.g., `"display"`, `"background-color"`) |
| `value` | string | `""` | Expected value (e.g., `"flex"`, `"#333"`) |

**Scoring:** 100 if `property: ...value...` pattern found (case-insensitive), 0 otherwise

```json
{
  "name": "css_uses_property",
  "file": "css/styles.css",
  "parameters": [
    { "name": "prop", "value": "display" },
    { "name": "value", "value": "flex" }
  ]
}
```

---

### has_style

Counts occurrences of a CSS property declaration in the stylesheet.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `style` | string | `""` | CSS property name to count |
| `count` | integer | `0` | Minimum occurrences. If `0`, score is always 100. |

**Scoring:** `min(100, found_count / count × 100)`

```json
{
  "name": "has_style",
  "file": "css/styles.css",
  "parameters": [
    { "name": "style", "value": "margin" },
    { "name": "count", "value": 3 }
  ]
}
```

---

### count_over_usage

Checks that a text pattern does not appear more than `max_allowed` times. Use as a penalty to limit repetitive CSS.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | string | `""` | Text pattern to count |
| `max_allowed` | integer | `0` | Maximum allowed occurrences |

**Scoring:** 100 if count ≤ `max_allowed`, 0 otherwise

```json
{
  "name": "count_over_usage",
  "file": "css/styles.css",
  "parameters": [
    { "name": "text", "value": "!important" },
    { "name": "max_allowed", "value": 2 }
  ]
}
```

---

### check_id_selector_over_usage

Counts `#id` selectors in CSS (ignoring comments and content inside rule blocks) and checks they don't exceed a limit.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_allowed` | integer | `0` | Maximum allowed `#id` selectors |

**Scoring:** 100 if count ≤ `max_allowed`, 0 otherwise

```json
{
  "name": "check_id_selector_over_usage",
  "file": "css/styles.css",
  "parameters": [
    { "name": "max_allowed", "value": 3 }
  ]
}
```

---

### uses_relative_units

Checks that the CSS uses at least one relative unit: `em`, `rem`, `%`, `vh`, or `vw`.

**Parameters:** None

**Scoring:** 100 if any relative unit found, 0 otherwise

```json
{
  "name": "uses_relative_units",
  "file": "css/styles.css"
}
```

---

### check_media_queries

Checks that the CSS contains at least one `@media` rule.

**Parameters:** None

**Scoring:** 100 if `@media` found, 0 otherwise

```json
{
  "name": "check_media_queries",
  "file": "css/styles.css"
}
```

---

### check_flexbox_usage

Checks that the CSS uses flexbox (`display: flex` or `flex-` properties).

**Parameters:** None

**Scoring:** 100 if flexbox usage found, 0 otherwise

```json
{
  "name": "check_flexbox_usage",
  "file": "css/styles.css"
}
```

---

### count_unused_css_classes

Cross-references CSS class selectors with classes used in HTML. Detects classes defined in CSS but not used in HTML.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `html_file` | string | `""` | Path to the HTML file |
| `css_file` | string | `""` | Path to the CSS file |

**Scoring:** 100 if no unused classes, 0 if any unused classes found

!!! note "Cross-file test"
    This test reads both HTML and CSS files. It does not use the `file` field — instead, specify both files via parameters.

```json
{
  "name": "count_unused_css_classes",
  "parameters": [
    { "name": "html_file", "value": "index.html" },
    { "name": "css_file", "value": "css/styles.css" }
  ]
}
```

---

## JavaScript Tests

### js_uses_feature

Checks that a specific keyword or feature name appears in the JavaScript code.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `feature` | string | `""` | Text to search for (e.g., `"addEventListener"`, `"fetch"`, `"async"`) |

**Scoring:** 100 if found, 0 otherwise

```json
{
  "name": "js_uses_feature",
  "file": "js/app.js",
  "parameters": [
    { "name": "feature", "value": "addEventListener" }
  ]
}
```

---

### uses_forbidden_method

Checks that a specific method or keyword does **not** appear in the JavaScript code. Use as a penalty.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | `""` | Method/keyword to forbid (e.g., `"document.write"`, `"eval"`) |

**Scoring:** 0 if found (penalty), 100 if not found

```json
{
  "name": "uses_forbidden_method",
  "file": "js/app.js",
  "parameters": [
    { "name": "method", "value": "document.write" }
  ]
}
```

---

### count_global_vars

Counts top-level variable declarations (`var`, `let`, `const` at the start of a line) and checks they don't exceed a limit.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_allowed` | integer | `0` | Maximum allowed global variable declarations |

**Scoring:** 100 if count ≤ `max_allowed`, 0 otherwise

```json
{
  "name": "count_global_vars",
  "file": "js/app.js",
  "parameters": [
    { "name": "max_allowed", "value": 5 }
  ]
}
```

---

### js_uses_query_string_parsing

Checks that the JavaScript code uses URL query string parsing via `URLSearchParams` or `window.location.search`.

**Parameters:** None

**Scoring:** 100 if found, 0 otherwise

```json
{
  "name": "js_uses_query_string_parsing",
  "file": "js/app.js"
}
```

---

### js_has_json_array_with_id

Checks that the JavaScript code contains an array literal with objects that have a specific key, with at least `min_items` entries.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `required_key` | string | `""` | Key to look for in array objects (e.g., `"id"`, `"name"`) |
| `min_items` | integer | `0` | Minimum number of objects with the key. If `0`, score is always 100. |

**Scoring:** `min(100, found_items / min_items × 100)`

```json
{
  "name": "js_has_json_array_with_id",
  "file": "js/data.js",
  "parameters": [
    { "name": "required_key", "value": "id" },
    { "name": "min_items", "value": 5 }
  ]
}
```

---

### js_uses_dom_manipulation

Checks that specific DOM manipulation methods are used in the JavaScript code.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `methods` | list of strings | `[]` | DOM methods to look for (e.g., `["getElementById", "querySelector", "innerHTML"]`) |
| `required_count` | integer | `0` | Minimum total occurrences across all methods. If `0`, score is always 100. |

**Scoring:** `min(100, total_found / required_count × 100)`

```json
{
  "name": "js_uses_dom_manipulation",
  "file": "js/app.js",
  "parameters": [
    { "name": "methods", "value": ["getElementById", "querySelector", "createElement"] },
    { "name": "required_count", "value": 3 }
  ]
}
```

---

### has_no_js_framework

Checks that no JavaScript framework is used. Detects React, Vue, and Angular patterns in both HTML and JS files. Use as a penalty.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `html_file` | string | `""` | Path to the HTML file |
| `js_file` | string | `""` | Path to the JS file |

**Detected patterns:** `react.js`, `react.dom`, `ReactDOM.render`, `vue.js`, `new Vue`, `angular.js`, `@angular/core`

**Scoring:** 0 if any framework detected (penalty), 100 if none found

```json
{
  "name": "has_no_js_framework",
  "parameters": [
    { "name": "html_file", "value": "index.html" },
    { "name": "js_file", "value": "js/app.js" }
  ]
}
```

---

## Structure Tests

### check_project_structure

Checks that a specific file exists in the submission.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expected_structure` | string | `""` | Filename to look for in the submission |

**Scoring:** 100 if file exists, 0 otherwise

```json
{
  "name": "check_project_structure",
  "parameters": [
    { "name": "expected_structure", "value": "index.html" }
  ]
}
```

---

### check_dir_exists

Checks that a specific directory exists in the submission (i.e., at least one file has a path starting with the directory).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dir_path` | string | `""` | Directory path to look for (e.g., `"css"`, `"js"`, `"images"`) |

**Scoring:** 100 if directory exists, 0 otherwise

```json
{
  "name": "check_dir_exists",
  "parameters": [
    { "name": "dir_path", "value": "css" }
  ]
}
```

---

## Complete Configuration Example

A landing page assignment testing HTML structure, CSS styling, JavaScript interactivity, and project organization:

```json
{
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "Project Structure",
        "weight": 10,
        "tests": [
          {
            "name": "check_project_structure",
            "parameters": [{ "name": "expected_structure", "value": "index.html" }],
            "weight": 34
          },
          {
            "name": "check_dir_exists",
            "parameters": [{ "name": "dir_path", "value": "css" }],
            "weight": 33
          },
          {
            "name": "check_dir_exists",
            "parameters": [{ "name": "dir_path", "value": "js" }],
            "weight": 33
          }
        ]
      },
      {
        "subject_name": "HTML",
        "weight": 40,
        "subjects": [
          {
            "subject_name": "Structure",
            "weight": 50,
            "tests": [
              {
                "name": "has_tag",
                "file": "index.html",
                "parameters": [
                  { "name": "tag", "value": "header" },
                  { "name": "required_count", "value": 1 }
                ],
                "weight": 25
              },
              {
                "name": "has_tag",
                "file": "index.html",
                "parameters": [
                  { "name": "tag", "value": "nav" },
                  { "name": "required_count", "value": 1 }
                ],
                "weight": 25
              },
              {
                "name": "has_tag",
                "file": "index.html",
                "parameters": [
                  { "name": "tag", "value": "main" },
                  { "name": "required_count", "value": 1 }
                ],
                "weight": 25
              },
              {
                "name": "has_tag",
                "file": "index.html",
                "parameters": [
                  { "name": "tag", "value": "footer" },
                  { "name": "required_count", "value": 1 }
                ],
                "weight": 25
              }
            ]
          },
          {
            "subject_name": "Accessibility",
            "weight": 50,
            "tests": [
              {
                "name": "check_all_images_have_alt",
                "file": "index.html",
                "weight": 50
              },
              {
                "name": "check_headings_sequential",
                "file": "index.html",
                "weight": 50
              }
            ]
          }
        ]
      },
      {
        "subject_name": "CSS",
        "weight": 30,
        "tests": [
          {
            "name": "check_css_linked",
            "file": "index.html",
            "weight": 20
          },
          {
            "name": "check_flexbox_usage",
            "file": "css/styles.css",
            "weight": 30
          },
          {
            "name": "check_media_queries",
            "file": "css/styles.css",
            "weight": 30
          },
          {
            "name": "uses_relative_units",
            "file": "css/styles.css",
            "weight": 20
          }
        ]
      },
      {
        "subject_name": "JavaScript",
        "weight": 20,
        "tests": [
          {
            "name": "js_uses_feature",
            "file": "js/app.js",
            "parameters": [{ "name": "feature", "value": "addEventListener" }],
            "weight": 50
          },
          {
            "name": "js_uses_dom_manipulation",
            "file": "js/app.js",
            "parameters": [
              { "name": "methods", "value": ["getElementById", "querySelector"] },
              { "name": "required_count", "value": 2 }
            ],
            "weight": 50
          }
        ]
      }
    ]
  },
  "penalty": {
    "weight": 15,
    "tests": [
      {
        "name": "check_no_inline_styles",
        "file": "index.html",
        "weight": 34
      },
      {
        "name": "check_bootstrap_usage",
        "file": "index.html",
        "weight": 33
      },
      {
        "name": "has_no_js_framework",
        "parameters": [
          { "name": "html_file", "value": "index.html" },
          { "name": "js_file", "value": "js/app.js" }
        ],
        "weight": 33
      }
    ]
  }
}
```
