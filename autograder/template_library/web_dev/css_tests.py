import re
from typing import Optional, List
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from sandbox_manager.sandbox_container import SandboxContainer


class CountUnusedCssClasses(TestFunction):
    @property
    def name(self):
        return "count_unused_css_classes"
    @property
    def description(self):
        return "Conta o número de classes CSS não utilizadas no código HTML e/ou CSS"
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", "O dicionário de arquivos enviados.", "dictionary"),
            ParamDescription("html_file", "Nome do arquivo HTML a ser analisado (ex: 'index.html').", "string"),
            ParamDescription("css_file", "Nome do arquivo CSS a ser analisado (ex: 'styles.css').", "string")
        ]
    def execute (self,submission_files, html_file: str, css_file: str) -> TestResult:
        html_content = submission_files.get(html_file, "")
        css_content = submission_files.get(css_file, "")
        if not html_content and not css_content:
            return TestResult(
                self.name, 
                0, 
                "Nenhum arquivo HTML ou CSS fornecido.", 
                {
                    "html_file": html_file, 
                    "css_file": css_file, 
                    "html_found": False, 
                    "css_found": False,
                    "unused_count": 0,
                    "category": "none"
                }
            )
        css_classes = set()
        if css_content:
            token_pattern = re.compile(
                r'(/\*.*?\*/)|'           # Comentaries (ignoring)
                r'(".*?")|'               # Double String (ignoring)
                r"('.*?')|"               # Simple String (ignoring)
                r'(\{)|'                  # Open brace
                r'(\})|'                  # Close brace
                r'(\.[a-zA-Z_-][\w-]*)',  # CSS class selector
                re.DOTALL
            )
            depth = 0
            for m in token_pattern.finditer(css_content):
                comment, double_str, simple_str, open_brace, close_brace, class_token = m.groups()
                if comment or double_str or simple_str:
                    continue
                if open_brace:
                    depth += 1
                    continue
                if close_brace:
                    depth = max(0, depth - 1)
                    continue
                if class_token and depth == 0:
                    css_classes.add(class_token[1:])
        used_classes = set()
        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            for el in soup.find_all(class_=True):
                for cls in el.get("class", []):
                    used_classes.add(cls)
        html_found = bool(html_content)
        css_found = bool(css_content)
        if html_found and css_found:
            unused_classes = sorted(css_classes - used_classes)
            category = "css_only_unused"
        elif css_found and not html_found:
            unused_classes = sorted(css_classes)
            category = "css_only_unused"
        elif html_found and not css_found:
            unused_classes = sorted(used_classes - css_classes)
            category = "html_classes_without_css"
        else:
            unused_classes = []
            category = "none"
        unused_count = len(unused_classes)
        score = 100 if unused_count == 0 else 0
        if category == "html_classes_without_css":
            report = (
                "Nenhuma classe no HTML sem definição em CSS."
                if unused_count == 0
                else f"{unused_count} classes encontradas no HTML sem definição em CSS: {unused_classes}"
            )
        else:
            report = (
                "Nenhuma classe CSS não utilizada encontrada."
                if unused_count == 0
                else f"{unused_count} classes CSS não utilizadas: {unused_classes}"
            )
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={
                "html_file": html_file,
                "css_file": css_file,
                "html_found": html_found,
                "css_found": css_found,
                "unused_count": unused_count,
                "unused_classes_sample": unused_classes[:20],
                "category": category
            }
        )

class CheckFlexboxUsage(TestFunction):
    @property
    def name(self):
        return "check_flexbox_usage"
    @property
    def description(self):
        return "Verifica se propriedades Flexbox são usadas no arquivo CSS."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"\b(display\s*:\s*flex|flex-)", css_content) is not None
        score = 100 if found else 0
        report = "Propriedades `flexbox` estão sendo utilizadas no CSS." if found else "Propriedades `flexbox` não foram encontradas no seu CSS."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CountOverUsage(TestFunction):
    @property
    def name(self):
        return "count_over_usage"
    @property
    def description(self):
        return "Penaliza o uso de uma string de texto específica se exceder uma contagem máxima permitida."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("text", "O texto a ser contado.", "string"),
            ParamDescription("max_allowed", "O número máximo de ocorrências permitidas.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], text: str = "", max_allowed: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found_count = css_content.count(text)
        score = 100 if found_count <= max_allowed else 0
        report = f"Uso exagerado de `{text}` detectado {found_count} vezes (máximo permitido: {max_allowed})." if score == 0 else f"Uso exagerado de `{text}` não detectado."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"text": text, "max_allowed": max_allowed}
        )

class UsesRelativeUnits(TestFunction):
    @property
    def name(self):
        return "uses_relative_units"
    @property
    def description(self):
        return "Verifica se o arquivo CSS usa unidades relativas como em, rem, %, vh, vw."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"\b(em|rem|%|vh|vw)\b", css_content) is not None
        score = 100 if found else 0
        report = "Estão sendo utilizadas medidas relativas no CSS." if found else "Não foram utilizadas medidas relativas como (em, rem, %, vh, vw) no seu CSS."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckIdSelectorOverUsage(TestFunction):
    @property
    def name(self):
        return "Check ID Selector Over Usage"
    @property
    def description(self):
        return "Conta seletores de ID válidos no CSS."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("max_allowed", "Número máximo de seletores de ID permitidos.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], max_allowed: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")
        css_content = files[0].content
        token_pattern = re.compile(
            r'(/\*.*?\*/)|'          # Comentaries (ignoring)
            r'("[^"]*")|'            # Double String (ignoring)
            r"('[^']*')|"            # Simple String (ignoring)
            r'(@media\b)|'           # @media
            r'(\{)|'                 # Open brace
            r'(\})|'                 # Close brace
            r'(#[a-zA-Z_][\w-]*)',   # Possible ID
            re.DOTALL | re.IGNORECASE
        )
        selectors = []
        context_stack = [True] 
        next_block_flag = False
        for match in token_pattern.finditer(css_content):
            comment, double_str, simple_str, media_key, open_brace, close_brace, found_id = match.groups()
            if comment or double_str or simple_str:
                continue
            if media_key:
                next_block_flag = True
            elif open_brace:
                context_stack.append(bool(next_block_flag))
                next_block_flag = False
            elif close_brace:
                if len(context_stack) > 1:
                    context_stack.pop()
            elif found_id:
                current_context_is_selector_area = context_stack[-1]
                if current_context_is_selector_area:
                    selectors.append(found_id)
        found_count = len(selectors)
        score = 100 if found_count <= max_allowed else 0
        report = f"{found_count} seletores de ID detectados (limite: {max_allowed})." if score == 0 else "Uso controlado de seletores de ID."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"max_allowed": max_allowed}
        )

class HasStyle(TestFunction):
    @property
    def name(self):
        return "has_style"
    @property
    def description(self):
        return "Verifica se uma regra de estilo CSS específica aparece um número mínimo de vezes."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("style", "A regra de estilo.", "string"),
            ParamDescription("count", "O número mínimo de ocorrências.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], style: str = "", count: int = 0, **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found_count = len(re.findall(rf"{re.escape(style)}\s*:\s*[^;]+;", css_content, re.IGNORECASE))
        score = min(100, int((found_count / count) * 100)) if count > 0 else 100
        report = f"Encontrados {found_count} de {count} `{style}` regras de estilização."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"style": style, "required_count": count}
        )

class CheckMediaQueries(TestFunction):
    @property
    def name(self):
        return "check_media_queries"
    @property
    def description(self):
        return "Verifica se existem media queries no arquivo CSS."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"@media\s+[^{]+\{", css_content) is not None
        score = 100 if found else 0
        report = "Media queries estão sendo utilizadas no CSS." if found else "Não foi encontrado o uso de media queries no seu CSS."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CssUsesProperty(TestFunction):
    @property
    def name(self):
        return "css_uses_property"
    @property
    def description(self):
        return "Verifica se um par de propriedade e valor CSS específico existe."
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("prop", "A propriedade CSS.", "string"),
            ParamDescription("value", "O valor esperado.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], prop: str = "", value: str = "", **kwargs) -> TestResult:
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        report = f"A propriedade `{prop}: {value};` foi encontrada." if found else f"A propriedade CSS `{prop}: {value};` não foi encontrada."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"prop": prop, "value": value}
        )

