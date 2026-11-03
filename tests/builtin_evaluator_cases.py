"""Every built-in static evaluator, with a passing and a failing project.

``builtin_evaluator_golden.json`` holds the per-criterion scores and reports
recorded by running these exact inputs on the pre-ARC-03 engine (main at
a938047, the old ``execute(files, sandbox, **kwargs)`` call shape). Tests
compare the migrated evaluators against it through the pipeline and HTTP.
The only edit is ``has-class``: the old engine listed found classes in set
order (hash-seed dependent); the migrated evaluator sorts them.
"""
import json
from pathlib import Path

GOLDEN = Path(__file__).with_name("builtin_evaluator_golden.json")


def _test(criterion_id, evaluator, parameters, **extra):
    return {"id": criterion_id, "type": evaluator, "name": criterion_id, "parameters": parameters, **extra}


WEBDEV_TESTS = [
    _test("has-class", "has_class", {"class_names": ["card", "btn-*"], "required_count": 2}),
    _test("bootstrap-linked", "check_bootstrap_linked", {}),
    _test("internal-links", "check_internal_links", {"required_count": 1}),
    _test("has-tag", "has_tag", {"tag": "section", "required_count": 2}),
    _test("forbidden-tag", "has_forbidden_tag", {"tag": "marquee"}),
    _test("has-attribute", "has_attribute", {"attribute": "aria-label", "required_count": 1}),
    _test("unclosed-tags", "check_no_unclosed_tags", {}),
    _test("inline-styles", "check_no_inline_styles", {}),
    _test("semantic-tags", "uses_semantic_tags", {}),
    _test("css-linked", "check_css_linked", {}),
    _test("css-property", "css_uses_property", {"prop": "display", "value": "flex"}),
    _test("over-usage", "count_over_usage", {"text": "!important", "max_allowed": 1}),
    _test("js-feature", "js_uses_feature", {"feature": "addEventListener"}),
    _test("forbidden-method", "uses_forbidden_method", {"method": "eval"}),
    _test("global-vars", "count_global_vars", {"max_allowed": 3}),
    _test("headings", "check_headings_sequential", {}),
    _test("images-alt", "check_all_images_have_alt", {}),
    _test("html-children", "check_html_direct_children", {}),
    _test("tag-not-inside", "check_tag_not_inside", {"child_tag": "div", "parent_tag": "p"}),
    _test("article-links", "check_internal_links_to_article", {"required_count": 1}),
    _test("has-style", "has_style", {"style": "margin", "count": 2}),
    _test("head-details", "check_head_details", {"detail_tag": "title"}),
    _test("attribute-value", "check_attribute_and_value", {"tag": "html", "attribute": "lang", "value": "en"}),
    _test("dir-exists", "check_dir_exists", {"dir_path": "assets"}),
    _test("project-structure", "check_project_structure", {"expected_structure": "assets/logo.svg"}),
    _test("id-selectors", "check_id_selector_over_usage", {"max_allowed": 1}),
    _test("relative-units", "uses_relative_units", {}),
    _test("media-queries", "check_media_queries", {}),
    _test("flexbox", "check_flexbox_usage", {}),
    _test("bootstrap-usage", "check_bootstrap_usage", {}),
    _test("query-param-links", "link_points_to_page_with_query_param",
          {"target_page": "detail.html", "query_param": "id", "required_count": 1}),
    _test("query-string", "js_uses_query_string_parsing", {}),
    _test("json-array", "js_has_json_array_with_id", {"required_key": "id", "min_items": 2}),
    _test("dom-manipulation", "js_uses_dom_manipulation",
          {"methods": ["createElement", "appendChild"], "required_count": 2}),
    _test("no-js-framework", "has_no_js_framework", {"html_file": "index.html", "js_file": "app.js"}),
    _test("unused-css", "count_unused_css_classes", {"html_file": "index.html", "css_file": "style.css"}),
]

STATIC_TESTS = [
    _test("forbidden-import", "forbidden_import", {"forbidden_imports": ["child_process"]}),
    _test("forbidden-keyword", "forbidden_keyword",
          {"forbidden_keywords": ["while_loop"], "custom_ast_grep_rules": [{"pattern": "debugger"}]}),
]

DEFINITION = {
    "schema_version": "1.0",
    "templates": ["webdev", "static_analysis"],
    "languages": ["node"],
    "criteria": {"base": {"weight": 100, "subjects": [
        {"subject_name": "Web", "weight": 80, "tests": WEBDEV_TESTS},
        {"subject_name": "Static", "weight": 20, "tests": STATIC_TESTS},
    ]}},
}

GOOD = {
    "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Catalog</title>
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body>
  <header><h1>Catalog</h1></header>
  <nav><a href="#intro" aria-label="Intro">Intro</a> <a href="#story">Story</a>
    <a href="detail.html?id=7">Detail</a></nav>
  <main class="container">
    <section id="intro" class="card"><h2>Intro</h2><p>Welcome.</p></section>
    <section class="card"><h2>More</h2><img src="assets/logo.svg" alt="Logo"></section>
    <article id="story"><h3>Story</h3><button class="btn-primary">Go</button></article>
  </main>
  <footer><p>Footer</p></footer>
  <script src="app.js"></script>
</body>
</html>
""",
    "style.css": """/* sizing uses rem units */
.container { display: flex; margin: 1rem; }
.card { margin: 2em; width: 50%; }
.btn-primary { padding: 1rem; }
#intro { color: blue; }
@media (max-width: 600px) { .container { flex-direction: column; } }
""",
    "app.js": """const items = [{ "id": 1, "name": "a" }, { "id": 2, "name": "b" }];
const params = new URLSearchParams(window.location.search);
document.addEventListener("DOMContentLoaded", () => {
  const list = document.createElement("ul");
  document.body.appendChild(list);
  for (const item of items) { console.log(item.id, params.get("id")); }
});
""",
    "assets/logo.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>",
}

BAD = {
    "index.html": """<html>
<div>stray</div>
<head></head>
<body>
  <h1>Title</h1>
  <h3>Skipped level</h3>
  <p style="color: red">Inline <div>block in paragraph</div></p>
  <marquee>Old</marquee>
  <img src="x.png">
  <span class="unused-one">x</span>
  <a href="#missing">Broken</a>
  <script src="https://cdn.example/react.js"></script>
  <div><p>unclosed
</body>
</html>
""",
    "style.css": """#a { color: red !important; }
#b { color: blue !important; }
#c { width: 100px; }
.ghost { height: 10px; }
""",
    "app.js": """var a = 1;
var b = 2;
var c = 3;
eval("a + b");
debugger;
while (a < 3) { a++; }
const cp = require('child_process');
ReactDOM.render(null, null);
""",
}

SUBMISSIONS = {"good": GOOD, "bad": BAD}


def leaves(tree):
    """Map criterion ID to (score, report) for a terminal outcome tree."""
    result = {}

    def walk(node):
        for test in node.get("tests") or []:
            result[test["id"]] = [round(test["score"], 6), test["report"]]
        for subject in node.get("subjects") or []:
            walk(subject)
    for category in ("base", "bonus", "penalty"):
        if tree.get(category):
            walk(tree[category])
    return result


def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))
