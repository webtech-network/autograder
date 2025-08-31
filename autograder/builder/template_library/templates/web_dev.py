import re
from bs4 import BeautifulSoup

from autograder.builder.template_library.templates.template import Template
from autograder.core.models.test_result import TestResult


# Assuming these classes are in their respective, importable files
# from autograder.builder.template_library.templates.template import Template
# from autograder.core.models.test_result import TestResult

class WebDevLibrary(Template):
    # ... (constructor and other unchanged methods)

    @staticmethod
    def has_tag(submission_files, tag: str, required_count: int) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = (
            f"Good job! Found {found_count} of {required_count} `<{tag}>` tags required." if score >= 100
            else f"Attention: Found {found_count} of {required_count} `<{tag}>` tags required."
        )
        return TestResult("has_tag", score, report, parameters={"tag": tag, "required_count": required_count})

    @staticmethod
    def has_attribute(submission_files, attribute: str, required_count: int) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(attrs={attribute: True}))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"The attribute `{attribute}` was found {found_count} time(s) out of {required_count} required."
        return TestResult("has_attribute", score, report, parameters={"attribute": attribute, "required_count": required_count})


    @staticmethod
    def has_structure(submission_files, tag_name: str) -> TestResult:
        result = WebDevLibrary.has_tag(submission_files, tag_name, 1)
        result.parameters = {"tag_name": tag_name} # Override parameters for clarity
        return result

    @staticmethod
    def check_no_unclosed_tags(submission_files) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        is_well_formed = soup.html and soup.body and soup.head
        score = 100 if is_well_formed else 20
        report = (
            "The HTML structure appears well-formed." if is_well_formed
            else "Problems in HTML structure, which may indicate unclosed tags."
        )
        return TestResult("check_no_unclosed_tags", score, report)

    @staticmethod
    def check_no_inline_styles(submission_files) -> TestResult:
        html_content = submission_files.get("index.html", "")
        found_count = len(BeautifulSoup(html_content, 'html.parser').find_all(style=True))
        score = 0 if found_count > 0 else 100
        report = (
            f"Penalty: Found {found_count} inline styles (`style='...'`). Move all style rules to your `.css` file." if found_count > 0
            else "Excellent! No inline styles found."
        )
        return TestResult("check_no_inline_styles", score, report)

    @staticmethod
    def check_viewport_meta_tag(submission_files) -> TestResult:
        result = WebDevLibrary.has_attribute(submission_files, "viewport", 1)
        # The original function call has no parameters, so we add none here.
        return result

    @staticmethod
    def uses_semantic_tags(submission_files) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(("article", "section", "nav", "aside", "figure")) is not None
        score = 100 if found else 40
        report = (
            "Good use of semantic tags detected." if found
            else "Consider using more semantic tags (`<article>`, `<section>`, `<nav>`) to improve your HTML structure."
        )
        return TestResult("uses_semantic_tags", score, report)

    @staticmethod
    def check_css_linked(submission_files) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", rel="stylesheet") is not None
        score = 100 if found else 0
        report = (
            "CSS file is correctly linked in the HTML." if found
            else "No `<link rel='stylesheet'>` tag found in your HTML."
        )
        return TestResult("check_css_linked", score, report)

    @staticmethod
    def css_uses_property(submission_files, prop: str, value: str) -> TestResult:
        css_content = submission_files.get("style.css", "")
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        report = (
            f"The property `{prop}: {value};` was used." if found
            else f"The CSS property `{prop}: {value};` was not found."
        )
        return TestResult("css_uses_property", score, report, parameters={"prop": prop, "value": value})

    @staticmethod
    def count_usage(submission_files, text: str, max_allowed: int) -> TestResult:
        css_content = submission_files.get("style.css", "")
        found_count = css_content.count(text)
        score = 0 if found_count > max_allowed else 100
        report = (
            f"Penalty: Usage of `{text}` detected {found_count} time(s) (max allowed: {max_allowed})." if score == 0
            else f"Great! No improper usage of `{text}` detected."
        )
        return TestResult("count_usage", score, report, parameters={"text": text, "max_allowed": max_allowed})

    @staticmethod
    def js_uses_feature(submission_files, feature: str) -> TestResult:
        js_content = submission_files.get("script.js", "")
        found = feature in js_content
        score = 100 if found else 0
        report = (
            f"The feature `{feature}` was implemented." if found
            else f"The JavaScript feature `{feature}` was not found in your code."
        )
        return TestResult("js_uses_feature", score, report, parameters={"feature": feature})

    @staticmethod
    def uses_forbidden_method(submission_files, method: str, count: int) -> TestResult:
        js_content = submission_files.get("script.js", "")
        found = method in js_content
        score = 100 if found else 0
        report = (
            f"Penalty: Forbidden method `{method}()` detected." if found
            else f"Great! Forbidden method `{method}()` was not used."
        )
        return TestResult("uses_forbidden_method", score, report, parameters={"method": method, "count": count})

    @staticmethod
    def count_global_vars(submission_files, max_allowed: int) -> TestResult:
        js_content = submission_files.get("script.js", "")
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        report = (
            f"Attention: {found_count} global variables detected (max allowed: {max_allowed})." if score == 0
            else "Good job keeping the global scope clean."
        )
        return TestResult("count_global_vars", score, report, parameters={"max_allowed": max_allowed})

    @staticmethod
    def check_headings_sequential(submission_files) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        headings = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        is_sequential = all(headings[i] <= headings[i + 1] for i in range(len(headings) - 1))
        score = 100 if is_sequential else 30
        report = (
            "Heading hierarchy is well structured." if is_sequential
            else "Heading order (`<h1>`, `<h2>`, etc.) is not sequential. Avoid skipping levels."
        )
        return TestResult("check_headings_sequential", score, report)

    @staticmethod
    def check_all_images_have_alt(submission_files) -> TestResult:
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all("img")
        if not images:
            return TestResult("check_all_images_have_alt", 100, "No images found to check.")
        with_alt = sum(1 for img in images if img.has_attr('alt') and img['alt'].strip())
        score = int((with_alt / len(images)) * 100)
        report = f"{with_alt} of {len(images)} images have the `alt` attribute, which is essential for accessibility."
        return TestResult("check_all_images_have_alt", score, report)