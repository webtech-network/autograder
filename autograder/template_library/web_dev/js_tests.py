import re
from typing import Optional, List

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from sandbox_manager.sandbox_container import SandboxContainer


class CountGlobalVars(TestFunction):
    """Counts variables in the global scope of JS."""
    @property
    def name(self):
        return "count_global_vars"
    @property
    def description(self):
        return "Conta o número de variáveis declaradas no escopo global."
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("max_allowed", "O número máximo de variáveis globais permitidas.", "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, max_allowed: int = 0, **kwargs) -> TestResult:
        """Executes the global variable count."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No JavaScript file provided.")

        js_content = files[0].content
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        report = f"Atenção: {found_count} variáveis globais detectadas (máximo permitido: {max_allowed})." if score == 0 else "Bom trabalho mantendo o escopo global limpo."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"max_allowed": max_allowed}
        )

class HasNoJsFramework(TestFunction):
    """Checks if forbidden JS frameworks are present."""
    @property
    def name(self):
        return "has_no_js_framework"
    @property
    def description(self):
        return "Verifica a presença de frameworks JavaScript proibidos (React, Vue, Angular)."
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", "O dicionário de arquivos enviados.", "dictionary"),
            ParamDescription("html_file", "O nome do arquivo HTML a ser analisado.", "string"),
            ParamDescription("js_file", "O nome do arquivo JavaScript a ser analisado.", "string")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, html_file: str = "", js_file: str = "", **kwargs) -> TestResult:
        """Executes the framework verification."""
        if not files:
            return TestResult(self.name, 0, "No files provided.")

        # Build a dictionary of files
        submission_files = {f.filename: f.content for f in files}

        # Combine content for a single search
        html_content = submission_files.get(html_file, "")
        js_content = submission_files.get(js_file, "")
        combined_content = html_content + js_content
        forbidden_patterns = [
            "react.js", "react.dom", "ReactDOM.render",  # React
            "vue.js", "new Vue",  # Vue
            "angular.js", "@angular/core",  # Angular
        ]
        found = any(pattern in combined_content for pattern in forbidden_patterns)
        score = 0 if found else 100  # Penalty test: score is 0 if found
        report = "Uso de framework JavaScript (React, Vue, Angular) detectado. O uso de frameworks não é permitido nesta atividade." if found else "Ótimo! Nenhum framework JavaScript proibido foi detectado."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class JsUsesQueryStringParsing(TestFunction):
    """Checks for query string reading in JS."""
    @property
    def name(self):
        return "js_uses_query_string_parsing"
    @property
    def description(self):
        return "Verifica se o código JavaScript contém padrões para ler query strings da URL."
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return []

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, **kwargs) -> TestResult:
        """Executes the query string pattern search."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No JavaScript file provided.")

        js_content = files[0].content
        # Regex to find 'URLSearchParams' or 'window.location.search'
        pattern = re.compile(r"URLSearchParams|window\.location\.search")
        found = pattern.search(js_content) is not None
        score = 100 if found else 0
        report = "O código JavaScript implementa a leitura de parâmetros da URL." if found else "Não foi encontrada a lógica para ler parâmetros da URL (ex: URLSearchParams) no seu JavaScript."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class UsesForbiddenMethod(TestFunction):
    """Checks and penalizes the use of forbidden methods."""
    @property
    def name(self):
        return "uses_forbidden_method"
    @property
    def description(self):
        return "Verifica e penaliza o uso de um método ou palavra-chave proibida."
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("method", "O nome do método proibido.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, method: str = "", **kwargs) -> TestResult:
        """Executes the search for forbidden methods."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No JavaScript file provided.")

        js_content = files[0].content
        found = method in js_content
        score = 0 if found else 100
        report = f"Penalidade: Método proibido `{method}()` detectado." if found else f"Ótimo! O método proibido `{method}()` não foi usado."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"method": method}
        )

class JsUsesFeature(TestFunction):
    """Checks if a specific JS feature is present."""
    @property
    def name(self): return "js_uses_feature"
    @property
    def description(self): return "Realiza uma busca de string simples para verificar se uma funcionalidade específica está presente."
    @property
    def required_file(self): return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("feature", "A funcionalidade a ser pesquisada.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, feature: str = "", **kwargs) -> TestResult:
        """Executes the search for features (literal string)."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No JavaScript file provided.")

        js_content = files[0].content
        found = feature in js_content
        score = 100 if found else 0
        report = f"A funcionalidade `{feature}` foi implementada." if found else f"A funcionalidade JavaScript `{feature}` não foi encontrada no seu código."
        return TestResult(
            test_name=self.name,
            score=score, report=report,
            parameters={"feature": feature}
        )

class JsUsesDomManipulation(TestFunction):
    """Checks for the use of DOM manipulation methods."""
    @property
    def name(self):
        return "js_uses_dom_manipulation"
    @property
    def description(self):
        return "Verifica se o código JS usa um número mínimo de métodos comuns de manipulação do DOM."
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("methods", "Uma lista de métodos a serem pesquisados (ex: ['createElement', 'appendChild']).", "list of strings"),
            ParamDescription("required_count", "Número mínimo total de vezes que esses métodos devem aparecer.", "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, methods: list = None, required_count: int = 0, **kwargs) -> TestResult:
        """Executes the search for DOM manipulations."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No JavaScript file provided.")

        js_content = files[0].content
        if methods is None:
            methods = []
        found_count = 0
        for method in methods:
            found_count += len(re.findall(r"\." + re.escape(method), js_content))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"Foram encontradas {found_count} de {required_count} chamadas a métodos de manipulação do DOM necessárias."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"methods": methods, "required_count": required_count}
        )

class JsHasJsonArrayWithId(TestFunction):
    """Checks for the existence of an array of objects with mandatory keys."""
    @property
    def name(self):
        return "js_has_json_array_with_id"
    @property
    def description(self):
        return "Verifica a existência de um array de objetos JS onde cada objeto possui uma chave específica obrigatória."
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("required_key", "A chave que deve existir em cada objeto (ex: 'id').", "string"),
            ParamDescription("min_items", "O número mínimo de itens esperados no array.", "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, required_key: str = "", min_items: int = 0, **kwargs) -> TestResult:
        """Executes the JSON structure check in JS."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No JavaScript file provided.")

        js_content = files[0].content
        # Regex to find an array assignment: var/let/const variable = [...]
        # It captures the content of the array
        match = re.search(r"(?:var|let|const)\s+\w+\s*=\s*(\[.*?\]);?", js_content, re.DOTALL)
        if not match:
            return TestResult(
                test_name=self.name,
                score=0,
                report="Não foi encontrada uma estrutura de dados (array) no formato JSON em seu arquivo JavaScript.",
                parameters={"required_key": required_key, "min_items": min_items}
            )
        array_content = match.group(1)
        # A simple heuristic: count how many times the required key appears as a key
        key_pattern = rf'"{required_key}"\s*:'
        found_items = len(re.findall(key_pattern, array_content))
        score = min(100, int((found_items / min_items) * 100)) if min_items > 0 else 100
        report = f"Encontrada estrutura de dados com {found_items} de {min_items} itens necessários, todos com a chave '{required_key}'."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"required_key": required_key, "min_items": min_items}
        )
