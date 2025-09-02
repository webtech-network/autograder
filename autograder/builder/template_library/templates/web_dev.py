import re
from bs4 import BeautifulSoup

from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction

from autograder.core.models.test_result import TestResult


# ===============================================================
# region: Concrete TestFunction Implementations
# ===============================================================

class HasTag(TestFunction):
    @property
    def name(self): return "has_tag"
    @property
    def description(self): return "Verifies that a specific HTML tag appears a minimum number of times."
    @property
    def parameter_description(self):
        return {
            "html_content": "The HTML content to analyze.",
            "tag": "The HTML tag to search for (e.g., 'div').",
            "required_count": "The minimum number of times the tag must appear."
        }
    def execute(self, html_content: str, tag: str, required_count: int) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"Foram encontradas {found_count} de {required_count} tags `<{tag}>` necessárias."
        return TestResult(self.name, score, report, parameters={"tag": tag, "required_count": required_count})

class HasForbiddenTag(TestFunction):
    @property
    def name(self): return "has_forbidden_tag"
    @property
    def description(self): return "Checks for the presence of a forbidden HTML tag."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze.", "tag": "The forbidden HTML tag to search for."}
    def execute(self, html_content: str, tag: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(tag) is not None
        score = 0 if found else 100
        report = f"A tag `<{tag}>` foi encontrada e é proibida." if found else f"A tag `<{tag}>` não foi encontrada, ótimo!"
        return TestResult(self.name, score, report, parameters={"tag": tag})

class HasAttribute(TestFunction):
    @property
    def name(self): return "has_attribute"
    @property
    def description(self): return "Checks if a specific HTML attribute is present on any tag, a minimum number of times."
    @property
    def parameter_description(self):
        return {
            "html_content": "The HTML content to analyze.",
            "attribute": "The attribute to search for (e.g., 'alt').",
            "required_count": "The minimum number of times the attribute must appear."
        }
    def execute(self, html_content: str, attribute: str, required_count: int) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(attrs={attribute: True}))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"O atributo `{attribute}` foi encontrado {found_count} vez(es) de {required_count} necessárias."
        return TestResult(self.name, score, report, parameters={"attribute": attribute, "required_count": required_count})

class CheckNoUnclosedTags(TestFunction):
    @property
    def name(self): return "check_no_unclosed_tags"
    @property
    def description(self): return "Performs a basic check for a well-formed HTML document."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        is_well_formed = soup.html and soup.body and soup.head
        score = 100 if is_well_formed else 20
        report = "Você possui uma boa estrutura HTML sem tags abertas." if is_well_formed else "Foram identificadas tags HTML abertas ou estrutura incorreta no seu arquivo."
        return TestResult(self.name, score, report)

class CheckNoInlineStyles(TestFunction):
    @property
    def name(self): return "check_no_inline_styles"
    @property
    def description(self): return "Ensures that no inline styles are used in the HTML file."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        found_count = len(BeautifulSoup(html_content, 'html.parser').find_all(style=True))
        score = 0 if found_count > 0 else 100
        report = f"Foi encontrado {found_count} inline styles (`style='...'`). Mova todas as regras de estilo para seu arquivo `.css`." if found_count > 0 else "Excelente! Nenhum estilo inline foi encontrado."
        return TestResult(self.name, score, report)

class UsesSemanticTags(TestFunction):
    @property
    def name(self): return "uses_semantic_tags"
    @property
    def description(self): return "Checks if the HTML uses at least one common semantic tag."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(("article", "section", "nav", "aside", "figure")) is not None
        score = 100 if found else 40
        report = "Utilizou tags semânticas." if found else "Não usou nenhuma tag do tipo (`<article>`, `<section>`, `<nav>`) na estrutura do HTML."
        return TestResult(self.name, score, report)

class CheckCssLinked(TestFunction):
    @property
    def name(self): return "check_css_linked"
    @property
    def description(self): return "Verifies that an external CSS stylesheet is linked in the HTML."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", rel="stylesheet") is not None
        score = 100 if found else 0
        report = "Arquivo CSS está corretamente linkado com o HTML." if found else "Não foi encontrada a tag `<link rel='stylesheet'>` no seu HTML."
        return TestResult(self.name, score, report)

class CssUsesProperty(TestFunction):
    @property
    def name(self): return "css_uses_property"
    @property
    def description(self): return "Checks if a specific CSS property and value pair exists."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze.", "prop": "The CSS property.", "value": "The expected value."}
    def execute(self, css_content: str, prop: str, value: str) -> TestResult:
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        report = f"A propriedade `{prop}: {value};` foi encontrada." if found else f"A propriedade CSS `{prop}: {value};` não foi encontrada."
        return TestResult(self.name, score, report, parameters={"prop": prop, "value": value})

class CountOverUsage(TestFunction):
    @property
    def name(self): return "count_over_usage"
    @property
    def description(self): return "Penalizes the use of a specific text string if it exceeds a maximum allowed count."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze.", "text": "The text to count.", "max_allowed": "The maximum allowed occurrences."}
    def execute(self, css_content: str, text: str, max_allowed: int) -> TestResult:
        found_count = css_content.count(text)
        score = 100 if found_count <= max_allowed else 0
        report = f"Uso exagerado de `{text}` detectado {found_count} vezes (máximo permitido: {max_allowed})." if score == 0 else f"Uso exagerado de `{text}` não detectado."
        return TestResult(self.name, score, report, parameters={"text": text, "max_allowed": max_allowed})

class JsUsesFeature(TestFunction):
    @property
    def name(self): return "js_uses_feature"
    @property
    def description(self): return "Performs a simple string search to check if a specific feature is present."
    @property
    def parameter_description(self): return {"js_content": "The JavaScript content to analyze.", "feature": "The feature to search for."}
    def execute(self, js_content: str, feature: str) -> TestResult:
        found = feature in js_content
        score = 100 if found else 0
        report = f"The feature `{feature}` was implemented." if found else f"The JavaScript feature `{feature}` was not found in your code."
        return TestResult(self.name, score, report, parameters={"feature": feature})

class UsesForbiddenMethod(TestFunction):
    @property
    def name(self): return "uses_forbidden_method"
    @property
    def description(self): return "Checks for and penalizes the use of a forbidden method or keyword."
    @property
    def parameter_description(self): return {"js_content": "The JavaScript content to analyze.", "method": "The forbidden method name."}
    def execute(self, js_content: str, method: str) -> TestResult:
        found = method in js_content
        score = 0 if found else 100
        report = f"Penalty: Forbidden method `{method}()` detected." if found else f"Great! Forbidden method `{method}()` was not used."
        return TestResult(self.name, score, report, parameters={"method": method})

class CountGlobalVars(TestFunction):
    @property
    def name(self): return "count_global_vars"
    @property
    def description(self): return "Counts the number of variables declared in the global scope."
    @property
    def parameter_description(self): return {"js_content": "The JavaScript content to analyze.", "max_allowed": "The maximum allowed global variables."}
    def execute(self, js_content: str, max_allowed: int) -> TestResult:
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        report = f"Attention: {found_count} global variables detected (max allowed: {max_allowed})." if score == 0 else "Good job keeping the global scope clean."
        return TestResult(self.name, score, report, parameters={"max_allowed": max_allowed})

class CheckHeadingsSequential(TestFunction):
    @property
    def name(self): return "check_headings_sequential"
    @property
    def description(self): return "Checks if heading levels are sequential and do not skip levels."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        headings = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        is_sequential = all(headings[i] <= headings[i + 1] for i in range(len(headings) - 1))
        score = 100 if is_sequential else 30
        report = "Heading hierarchy is well structured." if is_sequential else "Heading order (`<h1>`, `<h2>`, etc.) is not sequential. Avoid skipping levels."
        return TestResult(self.name, score, report)

class CheckAllImagesHaveAlt(TestFunction):
    @property
    def name(self): return "check_all_images_have_alt"
    @property
    def description(self): return "Verifies that all `<img>` tags have a non-empty `alt` attribute."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all("img")
        if not images:
            return TestResult(self.name, 100, "No images found to check.")
        with_alt = sum(1 for img in images if img.has_attr('alt') and img['alt'].strip())
        score = int((with_alt / len(images)) * 100)
        report = f"{with_alt} de {len(images)} imagens tem o atributo `alt` preenchido."
        return TestResult(self.name, score, report)

class CheckHtmlDirectChildren(TestFunction):
    @property
    def name(self): return "check_html_direct_children"
    @property
    def description(self): return "Ensures the only direct children of the `<html>` tag are `<head>` and `<body>`."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        html_tag = soup.find('html')
        if not html_tag:
            return TestResult(self.name, 0, "Tag <html> não encontrada.")
        children_names = [child.name for child in html_tag.findChildren(recursive=False) if child.name]
        is_valid = all(name in ['head', 'body'] for name in children_names) and 'head' in children_names and 'body' in children_names
        report = "Estrutura da tag <html> está correta." if is_valid else "A tag <html> deve conter apenas as tags <head> e <body> como filhos diretos."
        return TestResult(self.name, 100 if is_valid else 0, report)

class CheckTagNotInside(TestFunction):
    @property
    def name(self): return "check_tag_not_inside"
    @property
    def description(self): return "Checks that a specific tag is not nested anywhere inside another specific tag."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze.", "child_tag": "The child tag.", "parent_tag": "The parent tag."}
    def execute(self, html_content: str, child_tag: str, parent_tag: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        parent = soup.find(parent_tag)
        found = parent and parent.find(child_tag)
        report = f"A tag `<{child_tag}>` não deve ser usada dentro da tag `<{parent_tag}>`." if found else f"A tag `<{child_tag}>` não foi encontrada dentro da tag `<{parent_tag}>`."
        return TestResult(self.name, 0 if found else 100, report, parameters={"child_tag": child_tag, "parent_tag": parent_tag})

class CheckInternalLinksToArticle(TestFunction):
    @property
    def name(self): return "check_internal_links_to_article"
    @property
    def description(self): return "Checks for a minimum number of internal anchor links pointing to IDs on <article> tags."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze.", "required_count": "The minimum number of valid links."}
    def execute(self, html_content: str, required_count: int) -> TestResult:
        if not html_content:
            return TestResult(self.name, 0, "Arquivo home.html não encontrado.", parameters={"required_count": required_count})
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.select('a[href^="#"]')
        valid_links = 0
        for link in links:
            target_id = link['href'][1:]
            if not target_id: continue
            target_element = soup.find(id=target_id)
            if target_element and target_element.name == 'article':
                valid_links += 1
        score = min(100, int((valid_links / required_count) * 100))
        report = f"Encontrados {valid_links} de {required_count} links internos válidos para tags <article>."
        return TestResult(self.name, score, report, parameters={"required_count": required_count})

class HasStyle(TestFunction):
    @property
    def name(self): return "has_style"
    @property
    def description(self): return "Checks if a specific css style rule appears a minimum number of times."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze.", "style": "The style rule.", "count": "The minimum number of occurrences."}
    def execute(self, css_content: str, style: str, count: int) -> TestResult:
        found_count = len(re.findall(rf"{re.escape(style)}\s*:\s*[^;]+;", css_content, re.IGNORECASE))
        score = min(100, int((found_count / count) * 100)) if count > 0 else 100
        report = f"Encontrados {found_count} de {count} `{style}` regras de estilização."
        return TestResult(self.name, score, report, parameters={"style": style, "required_count": count})

class CheckHeadDetails(TestFunction):
    @property
    def name(self): return "check_head_details"
    @property
    def description(self): return "Checks if a specific detail tag exists within the <head> section."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze.", "detail_tag": "The tag to check for."}
    def execute(self, html_content: str, detail_tag: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        head = soup.find('head')
        if not head:
            return TestResult(self.name, 0, "Tag <head> não encontrada.")
        found = head.find(detail_tag) is not None
        score = 100 if found else 0
        report = f"A tag `<{detail_tag}>` foi encontrada na seção `<head>`." if found else f"A tag `<{detail_tag}>` não foi encontrada na seção `<head>`."
        return TestResult(self.name, score, report, parameters={"detail_tag": detail_tag})

class CheckAttributeAndValue(TestFunction):
    @property
    def name(self): return "check_attribute_and_value"
    @property
    def description(self): return "Checks if a specific HTML tag contains a specific attribute with a given value."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze.", "tag": "The tag.", "attribute": "The attribute.", "value": "The expected value."}
    def execute(self, html_content: str, tag: str, attribute: str, value: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.find_all(tag, attrs={attribute: value})
        score = 100 if elements else 0
        report = f"Encontrada a tag `<{tag}>` com `{attribute}='{value}'`." if score == 100 else f"Não foi encontrada a tag `<{tag}>` com `{attribute}='{value}'`."
        return TestResult(self.name, score, report, parameters={"tag": tag, "attribute": attribute, "value": value})

class CheckDirExists(TestFunction):
    @property
    def name(self): return "check_dir_exists"
    @property
    def description(self): return "Checks if a specific directory exists in the submission."
    @property
    def parameter_description(self): return {"submission_files": "The dictionary of submission files.", "dir_path": "The directory path."}
    def execute(self, submission_files: dict, dir_path: str) -> TestResult:
        exists = any(f.startswith(dir_path.rstrip('/') + '/') for f in submission_files.keys())
        score = 100 if exists else 0
        report = f"O diretório '{dir_path}' existe." if exists else f"O diretório '{dir_path}' não existe."
        return TestResult(self.name, score, report, parameters={"dir_path": dir_path})

class CheckProjectStructure(TestFunction):
    @property
    def name(self): return "check_project_structure"
    @property
    def description(self): return "Check if the expected structure path exists in the submission files."
    @property
    def parameter_description(self): return {"submission_files": "The dictionary of submission files.", "expected_structure": "The expected file path."}
    def execute(self, submission_files: dict, expected_structure: str) -> TestResult:
        exists = expected_structure in submission_files
        score = 100 if exists else 0
        report = f"O arquivo '{expected_structure}' existe." if exists else f"O arquivo '{expected_structure}' não existe."
        return TestResult(self.name, score, report, parameters={"expected_structure": expected_structure})

class CheckIdSelectorOverUsage(TestFunction):
    @property
    def name(self): return "check_id_selector_over_usage"
    @property
    def description(self): return "Counts the number of ID selectors used and penalizes if it exceeds max_allowed."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze.", "max_allowed": "The maximum allowed ID selectors."}
    def execute(self, css_content: str, max_allowed: int) -> TestResult:
        found_count = len(re.findall(r"#\w+", css_content))
        score = 100 if found_count <= max_allowed else 0
        report = f"{found_count} seletores de ID detectados (limite: {max_allowed})." if score == 0 else "Uso controlado de seletores de ID."
        return TestResult(self.name, score, report, parameters={"max_allowed": max_allowed})

class UsesRelativeUnits(TestFunction):
    @property
    def name(self): return "uses_relative_units"
    @property
    def description(self): return "Check if the css file uses relative units like em, rem, %, vh, vw."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze."}
    def execute(self, css_content: str) -> TestResult:
        found = re.search(r"\b(em|rem|%|vh|vw)\b", css_content) is not None
        score = 100 if found else 0
        report = "Estão sendo utilizadas medidas relativas no CSS." if found else "Não foram utilizadas medidas relativas como (em, rem, %, vh, vw) no seu CSS."
        return TestResult(self.name, score, report)

class CheckMediaQueries(TestFunction):
    @property
    def name(self): return "check_media_queries"
    @property
    def description(self): return "Checks if there are any media queries in the CSS file."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze."}
    def execute(self, css_content: str) -> TestResult:
        found = re.search(r"@media\s+[^{]+\{", css_content) is not None
        score = 100 if found else 0
        report = "Media queries estão sendo utilizadas no CSS." if found else "Não foi encontrado o uso de media queries no seu CSS."
        return TestResult(self.name, score, report)

class CheckFlexboxUsage(TestFunction):
    @property
    def name(self): return "check_flexbox_usage"
    @property
    def description(self): return "Checks if Flexbox properties are used in the CSS file."
    @property
    def parameter_description(self): return {"css_content": "The CSS content to analyze."}
    def execute(self, css_content: str) -> TestResult:
        found = re.search(r"\b(display\s*:\s*flex|flex-)", css_content) is not None
        score = 100 if found else 0
        report = "Propriedades `flexbox` estão sendo utilizadas no CSS." if found else "Propriedades `flexbox` não foram encontradas no seu CSS."
        return TestResult(self.name, score, report)

class CheckBootstrapUsage(TestFunction):
    @property
    def name(self): return "check_bootstrap_usage"
    @property
    def description(self): return "Checks if Bootstrap is linked in the HTML file."
    @property
    def parameter_description(self): return {"html_content": "The HTML content to analyze."}
    def execute(self, html_content: str) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", href=re.compile(r"bootstrap", re.IGNORECASE)) is not None or \
                soup.find("script", src=re.compile(r"bootstrap", re.IGNORECASE)) is not None
        score = 0 if found else 100
        report = "Você está usando bootstrap no seu CSS." if found else "Você não está usando bootstrap no seu CSS."
        return TestResult(self.name, score, report)


# ===============================================================
# endregion
# ===============================================================

class WebDevLibrary(Template):
    """
    A template for web development assignments, containing a collection of
    all available test functions related to HTML, CSS, and JS.
    """
    @property
    def template_name(self):
        return "Html Css Js Template"
    @property
    def template_description(self):
        return "A comprehensive template for web development assignments, including tests for HTML, CSS, and JavaScript."

    def __init__(self):
        self.tests = {
            "has_tag": HasTag(),
            "has_forbidden_tag": HasForbiddenTag(),
            "has_attribute": HasAttribute(),
            "check_no_unclosed_tags": CheckNoUnclosedTags(),
            "check_no_inline_styles": CheckNoInlineStyles(),
            "uses_semantic_tags": UsesSemanticTags(),
            "check_css_linked": CheckCssLinked(),
            "css_uses_property": CssUsesProperty(),
            "count_over_usage": CountOverUsage(),
            "js_uses_feature": JsUsesFeature(),
            "uses_forbidden_method": UsesForbiddenMethod(),
            "count_global_vars": CountGlobalVars(),
            "check_headings_sequential": CheckHeadingsSequential(),
            "check_all_images_have_alt": CheckAllImagesHaveAlt(),
            "check_html_direct_children": CheckHtmlDirectChildren(),
            "check_tag_not_inside": CheckTagNotInside(),
            "check_internal_links_to_article": CheckInternalLinksToArticle(),
            "has_style": HasStyle(),
            "check_head_details": CheckHeadDetails(),
            "check_attribute_and_value": CheckAttributeAndValue(),
            "check_dir_exists": CheckDirExists(),
            "check_project_structure": CheckProjectStructure(),
            "check_id_selector_over_usage": CheckIdSelectorOverUsage(),
            "uses_relative_units": UsesRelativeUnits(),
            "check_media_queries": CheckMediaQueries(),
            "check_flexbox_usage": CheckFlexboxUsage(),
            "check_bootstrap_usage": CheckBootstrapUsage(),
        }

    def get_test(self, name: str) -> TestFunction:
        """
        Retrieves a specific test function instance from the template.
        """
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function