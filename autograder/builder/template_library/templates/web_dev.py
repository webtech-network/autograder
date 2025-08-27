import re
from bs4 import BeautifulSoup
from autograder.core.models.test_result import TestResult
from autograder.builder.template_library.templates.template import Template
# ===============================================================
# 1. Test Library for Web Development (HTML, CSS, JS)
# ===============================================================

class WebDevLibrary(Template):
    """
    A collection of static methods to test HTML, CSS, and JavaScript files.
    The method signatures are designed to match the provided configuration file.
    """
    def __init__(self,template_name: str="web dev"):
        super().__init__(template_name)

    # --- HTML Structure and Validation ---

    @staticmethod
    def has_tag(submission_files, tag: str, required_count: int) -> TestResult:
        """Checks if the HTML file has at least a certain number of a given tag."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))

        # Proportional score based on the count
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100

        report = (
            f"Bom trabalho! Foram encontradas {found_count} de {required_count} tags <{tag}> necessárias." if score >= 100
            else f"Atenção: Foram encontradas {found_count} de {required_count} tags <{tag}> necessárias.")
        return TestResult("has_tag", score, report)

    @staticmethod
    def has_attribute(submission_files, attribute: str, required_count: int) -> TestResult:
        """Checks if the HTML file has at least a certain number of a given attribute."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(attrs={attribute: True}))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"O atributo '{attribute}' foi encontrado {found_count} vez(es) de {required_count} necessárias."
        return TestResult("has_attribute", score, report)

    @staticmethod
    def has_deprecated_tag(submission_files, tag: str, count: int) -> TestResult:
        """Checks for the usage of a deprecated HTML tag. The count is used as a penalty multiplier."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        score = 0 if found_count > 0 else 100  # It's a penalty, so any occurrence fails the test
        report = f"Penalidade: A tag obsoleta <{tag}> foi encontrada {found_count} vez(es)." if found_count > 0 else f"Ótimo! A tag obsoleta <{tag}> não foi utilizada."
        return TestResult("has_deprecated_tag", score, report)

    @staticmethod
    def has_structure(submission_files, tag_name: str) -> TestResult:
        """Checks for the presence of at least one of a structural semantic tag."""
        return WebDevLibrary.has_tag(submission_files, tag_name, 1)

    @staticmethod
    def check_no_unclosed_tags(submission_files) -> TestResult:
        """Validates that all HTML tags are properly closed."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        is_well_formed = soup.html and soup.body and soup.head
        score = 100 if is_well_formed else 20
        report = "A estrutura do HTML parece bem formada." if is_well_formed else "Problemas na estrutura do HTML, o que pode indicar tags não fechadas."
        return TestResult("check_no_unclosed_tags", score, report)

    @staticmethod
    def check_no_inline_styles(submission_files) -> TestResult:
        """Checks for the absence of inline 'style' attributes."""
        html_content = submission_files.get("index.html", "")
        found_count = len(BeautifulSoup(html_content, 'html.parser').find_all(style=True))
        score = 0 if found_count > 0 else 100
        report = f"Penalidade: Foram encontrados {found_count} estilos inline (style='...'). Mova todas as regras de estilo para seu arquivo .css." if found_count > 0 else "Excelente! Nenhum estilo inline foi encontrado."
        return TestResult("check_no_inline_styles", score, report)

    @staticmethod
    def check_viewport_meta_tag(submission_files) -> TestResult:
        """Ensures the viewport meta tag is present for responsiveness."""
        return WebDevLibrary.has_attribute(submission_files, "viewport", 1)

    @staticmethod
    def uses_semantic_tags(submission_files) -> TestResult:
        """Checks for the usage of semantic tags like <article>, <section>, etc."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(("article", "section", "nav", "aside", "figure")) is not None
        score = 100 if found else 40
        report = "Bom uso de tags semânticas detectado." if found else "Considere usar mais tags semânticas (<article>, <section>, <nav>) para melhorar a estrutura do seu HTML."
        return TestResult("uses_semantic_tags", score, report)

    # --- CSS Validation ---

    @staticmethod
    def check_css_linked(submission_files) -> TestResult:
        """Checks if a CSS stylesheet is linked in the HTML."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", rel="stylesheet") is not None
        score = 100 if found else 0
        report = "O arquivo CSS está corretamente linkado no HTML." if found else "Não foi encontrada a tag <link rel='stylesheet'> no seu HTML."
        return TestResult("check_css_linked", score, report)

    @staticmethod
    def css_uses_property(submission_files, prop: str, value: str) -> TestResult:
        """Checks if a specific CSS property is used."""
        css_content = submission_files.get("style.css", "")
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        report = f"A propriedade '{prop}: {value};' foi utilizada." if found else f"A propriedade CSS '{prop}: {value};' não foi encontrada."
        return TestResult("css_uses_property", score, report)

    @staticmethod
    def count_usage(submission_files, text: str, max_allowed: int) -> TestResult:
        """Generic counter for penalty checks. Score is 0 if count > max_allowed."""
        css_content = submission_files.get("style.css", "")
        found_count = css_content.count(text)
        score = 0 if found_count > max_allowed else 100
        report = f"Penalidade: O uso de '{text}' foi detectado {found_count} vez(es) (máximo permitido: {max_allowed})." if score == 0 else f"Ótimo! O uso indevido de '{text}' não foi detectado."
        return TestResult("count_usage", score, report)

    # --- JavaScript Validation ---

    @staticmethod
    def js_uses_feature(submission_files, feature: str) -> TestResult:
        """Checks if a specific JavaScript feature or keyword is used."""
        js_content = submission_files.get("script.js", "")
        found = feature in js_content
        score = 100 if found else 0
        report = f"O recurso '{feature}' foi implementado." if found else f"O recurso de JavaScript '{feature}' não foi encontrado no seu código."
        return TestResult("js_uses_feature", score, report)

    @staticmethod
    def uses_forbidden_method(submission_files, method: str, count: int) -> TestResult:
        """Penalty check for the use of forbidden JS methods like 'eval'."""
        js_content = submission_files.get("script.js", "")
        found = method in js_content
        score = 0 if found else 100
        report = f"Penalidade: O uso do método proibido '{method}()' foi detectado." if found else f"Ótimo! O método proibido '{method}()' não foi utilizado."
        return TestResult("uses_forbidden_method", score, report)

    @staticmethod
    def count_global_vars(submission_files, max_allowed: int) -> TestResult:
        """Counts potential global variables and penalizes if it exceeds a threshold."""
        js_content = submission_files.get("script.js", "")
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        report = f"Atenção: Foram detectadas {found_count} variáveis no escopo global (máximo permitido: {max_allowed})." if score == 0 else "Bom trabalho em manter o escopo global limpo."
        return TestResult("count_global_vars", score, report)

    # --- Accessibility ---

    @staticmethod
    def check_headings_sequential(submission_files) -> TestResult:
        """Checks if heading levels (h1, h2, etc.) are in a logical order."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        headings = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        is_sequential = all(headings[i] <= headings[i + 1] for i in range(len(headings) - 1))
        score = 100 if is_sequential else 30
        report = "A hierarquia de cabeçalhos está bem estruturada." if is_sequential else "A ordem dos cabeçalhos (<h1>, <h2>, etc.) não está sequencial. Evite pular níveis."
        return TestResult("check_headings_sequential", score, report)

    @staticmethod
    def check_all_images_have_alt(submission_files) -> TestResult:
        """Ensures all <img> tags have an 'alt' attribute."""
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all("img")
        if not images:
            return TestResult("check_all_images_have_alt", 100, "Nenhuma imagem encontrada para verificar.")

        with_alt = sum(1 for img in images if img.has_attr('alt') and img['alt'].strip())
        score = int((with_alt / len(images)) * 100)
        report = f"{with_alt} de {len(images)} imagens possuem o atributo 'alt', que é essencial para acessibilidade."
        return TestResult("check_all_images_have_alt", score, report)
