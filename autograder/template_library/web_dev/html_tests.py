import re
from typing import Optional, List
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from sandbox_manager.sandbox_container import SandboxContainer


class CheckHeadDetails(TestFunction):
    @property
    def name(self):
        return "check_head_details"
    @property
    def description(self):
        return "Verifica se uma tag de detalhe específica existe na seção `<head>`."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("detail_tag", "A tag a ser verificada.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], detail_tag: str = "", **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        head = soup.find('head')
        if not head:
            return TestResult(test_name=self.name, score=0, report="Tag <head> não encontrada.")
        found = head.find(detail_tag) is not None
        score = 100 if found else 0
        report = f"A tag `<{detail_tag}>` foi encontrada na seção `<head>`." if found else f"A tag `<{detail_tag}>` não foi encontrada na seção `<head>`."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"detail_tag": detail_tag}
        )

class HasForbiddenTag(TestFunction):
    @property
    def name(self):
        return "has_forbidden_tag"
    @property
    def description(self):
        return "Verifica a presença de uma tag HTML proibida."
    @property
    def required_file(self): 
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("tag", "A tag HTML proibida a ser pesquisada.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], tag: str = "", **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(tag) is not None
        score = 0 if found else 100
        report = f"A tag `<{tag}>` foi encontrada e é proibida." if found else f"A tag `<{tag}>` não foi encontrada, ótimo!"
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"tag": tag}
        )

class HasAttribute(TestFunction):
    @property
    def name(self):
        return "has_attribute"
    @property
    def description(self):
        return "Verifica se um atributo HTML específico está presente em qualquer tag, um número mínimo de vezes."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("attribute", "O atributo a ser pesquisado (por exemplo, 'alt').", "string"),
            ParamDescription("required_count", "O número mínimo de vezes que o atributo deve aparecer.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], attribute: str = "", required_count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(attrs={attribute: True}))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"O atributo `{attribute}` foi encontrado {found_count} vez(es) de {required_count} necessárias."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"attribute": attribute, "required_count": required_count}
        )

class CheckAttributeAndValue(TestFunction):
    @property
    def name(self):
        return "check_attribute_and_value"
    @property
    def description(self): 
        return "Verifica se uma tag HTML específica contém um atributo específico com um determinado valor."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("tag", "A tag.", "string"),
            ParamDescription("attribute", "O atributo.", "string"),
            ParamDescription("value", "O valor esperado.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], tag: str = "", attribute: str = "", value: str = "", **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.find_all(tag, attrs={attribute: value})
        score = 100 if elements else 0
        report = f"Encontrada a tag `<{tag}>` com `{attribute}='{value}'`." if score == 100 else f"Não foi encontrada a tag `<{tag}>` com `{attribute}='{value}'`."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"tag": tag, "attribute": attribute, "value": value}
        )

class CheckNoInlineStyles(TestFunction):
    @property
    def name(self):
        return "check_no_inline_styles"
    @property
    def description(self):
        return "Garante que nenhum estilo em linha (inline) seja usado no arquivo HTML."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        found_count = len(BeautifulSoup(html_content, 'html.parser').find_all(style=True))
        score = 0 if found_count > 0 else 100
        report = f"Foi encontrado {found_count} inline styles (`style='...'`). Mova todas as regras de estilo para seu arquivo `.css`." if found_count > 0 else "Excelente! Nenhum estilo inline foi encontrado."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckInternalLinks(TestFunction):
    @property
    def name(self):
        return "check_internal_links"
    @property
    def description(self):
        return "Verifica a existência de um número mínimo de links âncora internos que apontam para IDs de elementos válidos."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("required_count", "O número mínimo de links válidos.", "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], required_count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(
                test_name=self.name,
                score=0,
                report="Conteúdo HTML não encontrado.",
                parameters={"required_count": required_count}
            )

        html_content = files[0].content
        if not html_content:
            return TestResult(
                test_name=self.name,
                score=0,
                report="Conteúdo HTML não encontrado.",
                parameters={"required_count": required_count}
            )
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.select('a[href^="#"]')
        valid_links = 0
        for link in links:
            target_id = link['href'][1:]
            if not target_id: continue
            # Check if any element has this ID
            if soup.find(id=target_id):
                valid_links += 1
        score = min(100, int((valid_links / required_count) * 100)) if required_count > 0 else 100
        report = f"Encontrados {valid_links} de {required_count} links internos válidos ('âncoras')."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"required_count": required_count}
        )

class CheckNoUnclosedTags(TestFunction):
    @property
    def name(self):
        return "check_no_unclosed_tags"
    @property
    def description(self):
        return "Detecta tags HTML que foram abertas mas não foram fechadas."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
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
        report = (
            "Você possui uma boa estrutura HTML sem tags abertas."
            if unclosed == 0
            else f"Foram identificadas tags HTML abertas ou estrutura incorreta no seu arquivo."
        )
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class LinkPointsToPageWithQueryParam(TestFunction):
    @property
    def name(self):
        return "link_points_to_page_with_query_param"
    @property
    def description(self):
        return "Verifica a existência de tags âncora que levam a uma página específica com um parâmetro de query string obrigatório."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("target_page", "A página de destino esperada para o link (ex: 'detalhes.html').", "string"),
            ParamDescription("query_param", "O nome do parâmetro de query string a ser verificado (ex: 'id').", "string"),
            ParamDescription("required_count", "O número mínimo de links válidos que devem estar presentes.", "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], target_page: str = "", query_param: str = "", required_count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
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
        report = f"Encontrados {valid_link_count} de {required_count} links válidos para '{target_page}' com o parâmetro de consulta '{query_param}'."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"target_page": target_page, "query_param": query_param, "required_count": required_count}
        )

class CheckInternalLinksToArticle(TestFunction):
    @property
    def name(self):
        return "check_internal_links_to_article"
    @property
    def description(self):
        return "Verifica a existência de um número mínimo de links âncora internos apontando para IDs em tags `<article>`."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("required_count", "O número mínimo de links válidos.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], required_count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(
                test_name=self.name,
                score=0,
                report="Arquivo home.html não encontrado.",
                parameters={"required_count": required_count}
            )

        html_content = files[0].content
        if not html_content:
            return TestResult(
                test_name=self.name,
                score=0,
                report="Arquivo home.html não encontrado.",
                parameters={"required_count": required_count}
            )
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
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"required_count": required_count}
        )

class CheckTagNotInside(TestFunction):
    @property
    def name(self):
        return "check_tag_not_inside"
    @property
    def description(self):
        return "Verifica se uma tag específica não está aninhada em nenhum lugar dentro de outra tag específica."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("child_tag", "A tag filha.", "string"),
            ParamDescription("parent_tag", "A tag pai.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], child_tag: str = "", parent_tag: str = "", **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        parent = soup.find(parent_tag)
        found = parent and parent.find(child_tag)
        report = f"A tag `<{child_tag}>` não deve ser usada dentro da tag `<{parent_tag}>`." if found else f"A tag `<{child_tag}>` não foi encontrada dentro da tag `<{parent_tag}>`."
        return TestResult(
            test_name=self.name,
            score=0 if found else 100,
            report=report,
            parameters={"child_tag": child_tag, "parent_tag": parent_tag}
        )

class CheckHeadingsSequential(TestFunction):
    @property
    def name(self):
        return "check_headings_sequential"
    @property
    def description(self):
        return "Verifica se os níveis de cabeçalho não pulam níveis."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        headings = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        if len(headings) < 2:
            return TestResult(
                test_name=self.name,
                score=100,
                report="Apenas um nível de cabeçalho encontrado, portanto não há saltos."
            )
        valid = True
        for i in range(len(headings) - 1):
            current = headings[i]
            next_h = headings[i + 1]
            if next_h > current + 1:  
                valid = False
                break
        score = 100 if valid else 0
        report = (
            "A hierarquia de cabeçalhos está bem estruturada."
            if valid
            else "A ordem dos cabeçalhos (`<h1>`, `<h2>`, etc.) não é sequencial. Evite pular níveis."
        )
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasTag(TestFunction):
    @property
    def name(self):
        return "has_tag"
    @property
    def description(self):
        return "Verifica se uma tag HTML específica aparece um número mínimo de vezes."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("tag", "A tag HTML a ser pesquisada (por exemplo, 'div').", "string"),
            ParamDescription("required_count", "O número mínimo de vezes que a tag deve aparecer.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], tag: str = "", required_count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"Foram encontradas {found_count} de {required_count} tags `<{tag}>` necessárias."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"tag": tag, "required_count": required_count}
        )

class CheckBootstrapLinked(TestFunction):
    @property
    def name(self):
        return "check_bootstrap_linked"
    @property
    def description(self):
        return "Verifica se o framework Bootstrap (CSS ou JS) está vinculado no arquivo HTML."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", href=re.compile(r"bootstrap", re.IGNORECASE)) is not None or \
                soup.find("script", src=re.compile(r"bootstrap", re.IGNORECASE)) is not None
        score = 100 if found else 0
        report = "O framework Bootstrap foi encontrado no seu HTML." if found else "Não foi encontrado um link para o CSS ou JS do Bootstrap."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckBootstrapUsage(TestFunction):
    @property
    def name(self):
        return "check_bootstrap_usage"
    @property
    def description(self):
        return "Verifica se o Bootstrap está vinculado no arquivo HTML."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", href=re.compile(r"bootstrap", re.IGNORECASE)) is not None or \
                soup.find("script", src=re.compile(r"bootstrap", re.IGNORECASE)) is not None
        score = 0 if found else 100
        report = "Você está usando bootstrap no seu CSS." if found else "Você não está usando bootstrap no seu CSS."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class UsesSemanticTags(TestFunction):
    @property
    def name(self):
        return "uses_semantic_tags"
    @property
    def description(self):
        return "Verifica se o HTML usa pelo menos uma tag semântica comum."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(("article", "section", "nav", "aside", "figure")) is not None
        score = 100 if found else 40
        report = "Utilizou tags semânticas." if found else "Não usou nenhuma tag do tipo (`<article>`, `<section>`, `<nav>`) na estrutura do HTML."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckCssLinked(TestFunction):
    @property
    def name(self):
        return "check_css_linked"
    @property
    def description(self):
        return "Verifica se uma folha de estilo CSS externa está vinculada no HTML."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", rel="stylesheet") is not None
        score = 100 if found else 0
        report = "Arquivo CSS está corretamente linkado com o HTML." if found else "Não foi encontrada a tag `<link rel='stylesheet'>` no seu HTML."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckAllImagesHaveAlt(TestFunction):
    @property
    def name(self):
        return "check_all_images_have_alt"
    @property
    def description(self):
        return "Verifica se todas as tags `<img>` possuem um atributo `alt` não vazio."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all("img")
        if not images:
            return TestResult(test_name=self.name, score=100, report="Nenhuma imagem encontrada para verificar.")
        with_alt = sum(1 for img in images if img.has_attr('alt') and img['alt'].strip())
        score = int((with_alt / len(images)) * 100)
        report = f"{with_alt} de {len(images)} imagens tem o atributo `alt` preenchido."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasClass(TestFunction):
    @property
    def name(self):
        return "has_class"
    @property
    def description(self):
        return "Verifica a presença de classes CSS específicas, com suporte a curingas, um número mínimo de vezes."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return [
            ParamDescription("class_names", "Uma lista de nomes de classes a serem pesquisadas. Curingas (*) são suportados (por exemplo, 'col-*').", "list of strings"),
            ParamDescription("required_count", "O número mínimo de vezes que as classes devem aparecer no total.", "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], class_names: list[str] = None, required_count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = 0
        # Compile regex patterns from class names with wildcards
        patterns = [re.compile(name.replace('*', r'\S*')) for name in (class_names or [])]

        # Find all tags that have a 'class' attribute
        all_elements_with_class = soup.find_all(class_=True)
        found_classes = []
        for element in all_elements_with_class:
            # element['class'] is a list of all classes on that tag
            for pattern in patterns:
                for cls in element['class']:
                    if pattern.fullmatch(cls):
                        found_count += 1
                        found_classes.append(cls)
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"Foram encontradas {found_count} de {required_count} classes CSS necessárias. Classes encontradas: {list(set(found_classes))}"
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"class_names": class_names, "required_count": required_count})

class CheckHtmlDirectChildren(TestFunction):
    @property
    def name(self):
        return "check_html_direct_children"
    @property
    def description(self):
        return "Garante que os únicos filhos diretos da tag `<html>` são `<head>` e `<body>`."
    @property
    def required_file(self):
        return "HTML"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No HTML file provided.")

        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        html_tag = soup.find('html')
        if not html_tag:
            return TestResult(test_name=self.name, score=0, report="Tag <html> não encontrada.")
        children_names = [child.name for child in html_tag.findChildren(recursive=False) if child.name]
        is_valid = all(name in ['head', 'body'] for name in children_names) and 'head' in children_names and 'body' in children_names
        report = "Estrutura da tag <html> está correta." if is_valid else "A tag <html> deve conter apenas as tags <head> e <body> como filhos diretos."
        return TestResult(
            test_name=self.name,
            score=100 if is_valid else 0,
            report=report
        )

