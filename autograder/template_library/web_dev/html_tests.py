import re
from typing import Annotated, List, Optional
from urllib.parse import parse_qs, urlparse

from pydantic import Field

from autograder.models.abstract.test_function import EvaluationInput, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.template_library.web_dev.documents import parsed_html
from autograder.translations import t


class CheckHeadDetails(TestFunction):
    """Checks if a specific detail tag exists in the <head> section."""
    @property
    def name(self):
        return "check_head_details"
    @property
    def description(self):
        return t("web_dev.html.check_head.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                detail_tag: Annotated[str, Field(min_length=1, description=t("web_dev.html.check_head.param.detail_tag"))],
                ) -> TestResult:
        """Executes the detail tag verification test in the head."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        head = soup.find('head')
        found = head is not None and head.find(detail_tag) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.html.check_head.report.found", locale=locale, detail_tag=detail_tag) if found else t("web_dev.html.check_head.report.not_found", locale=locale, detail_tag=detail_tag)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasForbiddenTag(TestFunction):
    """Checks for the presence of a forbidden HTML tag."""
    absence_check = "Prohibition: passes while the forbidden tag is absent."
    @property
    def name(self):
        return "has_forbidden_tag"
    @property
    def description(self):
        return t("web_dev.html.has_forbidden_tag.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                tag: Annotated[str, Field(min_length=1, description=t("web_dev.html.has_forbidden_tag.param.tag"))],
                ) -> TestResult:
        """Executes the forbidden tag verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found = soup.find(tag) is not None
        score = 0 if found else 100
        locale = evaluation.locale
        report = t("web_dev.html.has_forbidden_tag.report.found", locale=locale, tag=tag) if found else t("web_dev.html.has_forbidden_tag.report.not_found", locale=locale, tag=tag)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasAttribute(TestFunction):
    """Checks if an HTML attribute is present a certain number of times."""
    @property
    def name(self):
        return "has_attribute"
    @property
    def description(self):
        return t("web_dev.html.has_attribute.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                attribute: Annotated[str, Field(min_length=1, description=t("web_dev.html.has_attribute.param.attribute"))],
                required_count: Annotated[int, Field(ge=1, description=t("web_dev.html.has_attribute.param.required_count"))] = 1,
                ) -> TestResult:
        """Executes the search for specific attributes."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found_count = len(soup.find_all(attrs={attribute: True}))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.html.has_attribute.report", locale=evaluation.locale, attribute=attribute, found_count=found_count, required_count=required_count)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckAttributeAndValue(TestFunction):
    """Checks if a tag contains an attribute with a specific value."""
    @property
    def name(self):
        return "check_attribute_and_value"
    @property
    def description(self): 
        return t("web_dev.html.check_attribute_and_value.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                tag: Annotated[str, Field(min_length=1, description=t("web_dev.html.check_attribute_and_value.param.tag"))],
                attribute: Annotated[str, Field(min_length=1, description=t("web_dev.html.check_attribute_and_value.param.attribute"))],
                value: Annotated[str, Field(min_length=1, description=t("web_dev.html.check_attribute_and_value.param.value"))],
                ) -> TestResult:
        """Executes the attribute and value verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        elements = soup.find_all(tag, attrs={attribute: value})
        score = 100 if elements else 0
        locale = evaluation.locale
        report = t("web_dev.html.check_attribute_and_value.report.found", locale=locale, tag=tag, attribute=attribute, value=value) if score == 100 else t("web_dev.html.check_attribute_and_value.report.not_found", locale=locale, tag=tag, attribute=attribute, value=value)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckNoInlineStyles(TestFunction):
    """Ensures that no inline styles are used."""
    absence_check = "Prohibition: passes while no element has an inline style."
    @property
    def name(self):
        return "check_no_inline_styles"
    @property
    def description(self):
        return t("web_dev.html.check_no_inline_styles.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the search for inline styles."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found_count = len(soup.find_all(style=True))
        score = 0 if found_count > 0 else 100
        locale = evaluation.locale
        report = t("web_dev.html.check_no_inline_styles.report.found", locale=locale, found_count=found_count) if found_count > 0 else t("web_dev.html.check_no_inline_styles.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckInternalLinks(TestFunction):
    """Checks for the existence of internal links (#id)."""
    @property
    def name(self):
        return "check_internal_links"
    @property
    def description(self):
        return t("web_dev.html.check_internal_links.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                required_count: Annotated[int, Field(ge=1, description="The minimum number of links that point to an existing element ID.")] = 1,
                ) -> TestResult:
        """Executes the internal link verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(
                test_name=self.name,
                score=0,
                report=t("web_dev.html.check_internal_links.report.no_content", locale=evaluation.locale)
            )

        html_content = files[0].content
        if not html_content:
            return TestResult(
                test_name=self.name,
                score=0,
                report=t("web_dev.html.check_internal_links.report.no_content", locale=evaluation.locale)
            )
        soup = parsed_html(files[0])
        links = soup.select('a[href^="#"]')
        valid_links = 0
        for link in links:
            target_id = link['href'][1:]
            if not target_id:
                continue
            # Check if any element has this ID
            if soup.find(id=target_id):
                valid_links += 1
        score = min(100, int((valid_links / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.html.check_internal_links.report.valid", locale=evaluation.locale, valid_links=valid_links, required_count=required_count)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckNoUnclosedTags(TestFunction):
    """Detector for unclosed HTML tags."""
    absence_check = "Prohibition: passes while no tag is left unclosed."
    @property
    def name(self):
        return "check_no_unclosed_tags"
    @property
    def description(self):
        return t("web_dev.html.check_no_unclosed_tags.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the search for unclosed tags."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        void_tags = {
            "area","base","br","col","embed","hr","img","input","link",
            "meta","param","source","track","wbr"
        }
        ignore_tags = {"html", "head", "body"}
        # Remove comentarios para evitar falsos positivos
        html_no_comments = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
        tag_pattern = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?>")
        open_tags = []
        for match in tag_pattern.finditer(html_no_comments):
            raw = match.group(0)
            tag = match.group(1).lower()
            if tag in void_tags or tag in ignore_tags:
                continue
            if raw.endswith("/>"):
                continue
            if raw.startswith("</"):
                # remove a ultima abertura correspondente
                for i in range(len(open_tags) - 1, -1, -1):
                    if open_tags[i] == tag:
                        del open_tags[i]
                        break
                continue
            open_tags.append(tag)
        unclosed = len(open_tags)
        score = 100 if unclosed == 0 else 0
        locale = evaluation.locale
        report = (
            t("web_dev.html.check_no_unclosed_tags.report.not_found", locale=locale)
            if unclosed == 0
            else t("web_dev.html.check_no_unclosed_tags.report.found", locale=locale)
        )
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class LinkPointsToPageWithQueryParam(TestFunction):
    """Checks links that lead to pages with query parameters."""
    @property
    def name(self):
        return "link_points_to_page_with_query_param"
    @property
    def description(self):
        return t("web_dev.html.link_points_to_page_with_query_param.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                target_page: Annotated[str, Field(min_length=1, description=t("web_dev.html.link_points_to_page_with_query_param.param.target_page"))],
                query_param: Annotated[str, Field(min_length=1, description=t("web_dev.html.link_points_to_page_with_query_param.param.query_param"))],
                required_count: Annotated[int, Field(ge=1, description=t("web_dev.html.link_points_to_page_with_query_param.param.required_count"))] = 1,
                ) -> TestResult:
        """Executes the verification of links with query parameters."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        links = soup.find_all("a", href=True)
        valid_link_count = 0
        for link in links:
            href = link['href']
            parsed_url = urlparse(href)
            # Check if the path matches the target page
            if parsed_url.path == target_page:
                # Parse query parameters and check if the required param exists
                query_params = parse_qs(parsed_url.query)
                if query_param in query_params:
                    valid_link_count += 1
        score = min(100, int((valid_link_count / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.html.link_points_to_page_with_query_param.report", locale=evaluation.locale, valid_link_count=valid_link_count, required_count=required_count, target_page=target_page, query_param=query_param)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckInternalLinksToArticle(TestFunction):
    """Checks internal links that point to <article> tags."""
    @property
    def name(self):
        return "check_internal_links_to_article"
    @property
    def description(self):
        return t("web_dev.html.check_internal_links_to_article.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                required_count: Annotated[int, Field(ge=1, description="The minimum number of links that point to the ID of an <article> element.")] = 1,
                ) -> TestResult:
        """Executes the verification of links to articles."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(
                test_name=self.name,
                score=0,
                report=t("web_dev.html.check_internal_links_to_article.report.no_file", locale=evaluation.locale)
            )

        html_content = files[0].content
        if not html_content:
            return TestResult(
                test_name=self.name,
                score=0,
                report=t("web_dev.html.check_internal_links_to_article.report.no_file", locale=evaluation.locale)
            )
        soup = parsed_html(files[0])
        links = soup.select('a[href^="#"]')
        valid_links = 0
        for link in links:
            target_id = link['href'][1:]
            if not target_id:
                continue
            target_element = soup.find(id=target_id)
            if target_element and target_element.name == 'article':
                valid_links += 1
        score = min(100, int((valid_links / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.html.check_internal_links_to_article.report.valid", locale=evaluation.locale, valid_links=valid_links, required_count=required_count)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckTagNotInside(TestFunction):
    """Ensures that a tag is not inside another."""
    absence_check = "Prohibition: passes while the child tag never appears inside the parent tag."
    @property
    def name(self):
        return "check_tag_not_inside"
    @property
    def description(self):
        return t("web_dev.html.check_tag_not_inside.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                child_tag: Annotated[str, Field(min_length=1, description=t("web_dev.html.check_tag_not_inside.param.child_tag"))],
                parent_tag: Annotated[str, Field(min_length=1, description=t("web_dev.html.check_tag_not_inside.param.parent_tag"))],
                ) -> TestResult:
        """Executes the forbidden nesting verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        parent = soup.find(parent_tag)
        found = parent and parent.find(child_tag)
        score = 0 if found else 100
        locale = evaluation.locale
        report = t("web_dev.html.check_tag_not_inside.report.found", locale=locale, child_tag=child_tag, parent_tag=parent_tag) if found else t("web_dev.html.check_tag_not_inside.report.not_found", locale=locale, child_tag=child_tag, parent_tag=parent_tag)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckHeadingsSequential(TestFunction):
    """Checks if heading levels (h1-h6) are sequential."""
    absence_check = "Rule over headings: passes while no heading level is skipped, including pages with fewer than two levels."
    @property
    def name(self):
        return "check_headings_sequential"
    @property
    def description(self):
        return t("web_dev.html.check_headings_sequential.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the heading sequence verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        headings = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        if len(headings) < 2:
            return TestResult(
                test_name=self.name,
                score=100,
                report=t("web_dev.html.check_headings_sequential.report.one_level", locale=evaluation.locale)
            )
        valid = True
        for i in range(len(headings) - 1):
            current = headings[i]
            next_h = headings[i + 1]
            if next_h > current + 1:  
                valid = False
                break
        score = 100 if valid else 0
        locale = evaluation.locale
        report = (
            t("web_dev.html.check_headings_sequential.report.valid", locale=locale)
            if valid
            else t("web_dev.html.check_headings_sequential.report.invalid", locale=locale)
        )
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasTag(TestFunction):
    """Checks if an HTML tag appears a minimum number of times."""
    @property
    def name(self):
        return "has_tag"
    @property
    def description(self):
        return t("web_dev.html.has_tag.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                tag: Annotated[str, Field(min_length=1, description=t("web_dev.html.has_tag.param.tag"))],
                required_count: Annotated[int, Field(ge=1, description=t("web_dev.html.has_tag.param.required_count"))] = 1,
                ) -> TestResult:
        """Executes the tag presence verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found_count = len(soup.find_all(tag))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.html.has_tag.report", locale=evaluation.locale, found_count=found_count, required_count=required_count, tag=tag)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckBootstrapLinked(TestFunction):
    """Checks if Bootstrap is linked."""
    @property
    def name(self):
        return "check_bootstrap_linked"
    @property
    def description(self):
        return t("web_dev.html.check_bootstrap_linked.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the Bootstrap link verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found = soup.find("link", href=re.compile(r"bootstrap", re.IGNORECASE)) is not None or \
                soup.find("script", src=re.compile(r"bootstrap", re.IGNORECASE)) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.html.check_bootstrap_linked.report.found", locale=locale) if found else t("web_dev.html.check_bootstrap_linked.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckBootstrapUsage(TestFunction):
    """Checks if Bootstrap is being used."""
    absence_check = "Prohibition: passes while Bootstrap is not used."
    @property
    def name(self):
        return "check_bootstrap_usage"
    @property
    def description(self):
        return t("web_dev.html.check_bootstrap_usage.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the Bootstrap usage verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found = soup.find("link", href=re.compile(r"bootstrap", re.IGNORECASE)) is not None or \
                soup.find("script", src=re.compile(r"bootstrap", re.IGNORECASE)) is not None
        score = 0 if found else 100
        locale = evaluation.locale
        report = t("web_dev.html.check_bootstrap_usage.report.found", locale=locale) if found else t("web_dev.html.check_bootstrap_usage.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class UsesSemanticTags(TestFunction):
    """Checks if the HTML uses semantic tags."""
    @property
    def name(self):
        return "uses_semantic_tags"
    @property
    def description(self):
        return t("web_dev.html.uses_semantic_tags.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the semantic tags verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found = soup.find(("article", "section", "nav", "aside", "figure")) is not None
        score = 100 if found else 40
        locale = evaluation.locale
        report = t("web_dev.html.uses_semantic_tags.report.found", locale=locale) if found else t("web_dev.html.uses_semantic_tags.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckCssLinked(TestFunction):
    """Checks if CSS is linked."""
    @property
    def name(self):
        return "check_css_linked"
    @property
    def description(self):
        return t("web_dev.html.check_css_linked.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the CSS link verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found = soup.find("link", rel="stylesheet") is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.html.check_css_linked.report.found", locale=locale) if found else t("web_dev.html.check_css_linked.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckAllImagesHaveAlt(TestFunction):
    """Checks if all images have an alt attribute."""
    absence_check = "Rule over images: passes while no image lacks alt text, including pages without images."
    @property
    def name(self):
        return "check_all_images_have_alt"
    @property
    def description(self):
        return t("web_dev.html.check_all_images_have_alt.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the alt attribute verification in images."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        images = soup.find_all("img")
        if not images:
            return TestResult(test_name=self.name, score=100, report=t("web_dev.html.check_all_images_have_alt.report.no_images", locale=evaluation.locale))
        with_alt = sum(1 for img in images if img.has_attr('alt') and img['alt'].strip())
        score = int((with_alt / len(images)) * 100) if len(images) > 0 else 100
        report = t("web_dev.html.check_all_images_have_alt.report.valid", locale=evaluation.locale, with_alt=with_alt, total_images=len(images))
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasClass(TestFunction):
    """Checks for the presence of specific CSS classes (supports wildcards)."""
    @property
    def name(self):
        return "has_class"
    @property
    def description(self):
        return t("web_dev.html.has_class.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def _compile_patterns(self, class_names: Optional[List[str]]) -> List[re.Pattern]:
        """Helper to compile regex patterns for classes."""
        return [re.compile(name.replace('*', r'\S*')) for name in (class_names or [])]

    def execute(self, evaluation: EvaluationInput, *,
                class_names: Annotated[List[Annotated[str, Field(min_length=1)]], Field(min_length=1, description=t("web_dev.html.has_class.param.class_names"))],
                required_count: Annotated[int, Field(ge=1, description=t("web_dev.html.has_class.param.required_count"))] = 1,
                ) -> TestResult:
        """Executes the search for CSS classes in the HTML."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        found_count = 0
        patterns = self._compile_patterns(class_names)
        found_classes = []
        for element in soup.find_all(class_=True):
            for pattern in patterns:
                for cls in element['class']:
                    if pattern.fullmatch(cls):
                        found_count += 1
                        found_classes.append(cls)
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.html.has_class.report", locale=evaluation.locale, found_count=found_count, required_count=required_count, classes=sorted(set(found_classes)))
        return TestResult(
            test_name=self.name,
            score=score,
            report=report)

class CheckHtmlDirectChildren(TestFunction):
    """Ensures that <html> has only <head> and <body> as first-level children."""
    @property
    def name(self):
        return "check_html_direct_children"
    @property
    def description(self):
        return t("web_dev.html.check_html_direct_children.description")
    file_extensions = (".html", ".htm")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the direct structure verification of <html>."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        soup = parsed_html(files[0])
        html_tag = soup.find('html')
        if not html_tag:
            return TestResult(test_name=self.name, score=0, report=t("web_dev.html.check_html_direct_children.report.no_html", locale=evaluation.locale))
        children_names = [child.name for child in html_tag.findChildren(recursive=False) if child.name]
        is_valid = all(name in ['head', 'body'] for name in children_names) and 'head' in children_names and 'body' in children_names
        locale = evaluation.locale
        report = t("web_dev.html.check_html_direct_children.report.valid", locale=locale) if is_valid else t("web_dev.html.check_html_direct_children.report.invalid", locale=locale)
        return TestResult(
            test_name=self.name,
            score=100 if is_valid else 0,
            report=report
        )
