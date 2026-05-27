import logging 
from typing import List, Optional, Dict, Any, Type
from pydantic import BaseModel, Field

from autograder.models.abstract.template import Template
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.dataclass.structural_analysis_result import StructuralAnalysisResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language
import re

# ===============================================================
# TestFunction for Forbidden Import Detection
# ===============================================================

class ForbiddenImportTest(TestFunction):
    """
    Tests that a submission does NOT import any of the specified forbidden libraries.

    Performs static analysis on submission file contents using language-aware
    regex patterns. Supports Python, Java, JavaScript/Node, C and C++.
    """

    # Language-specific regex builders: each returns a compiled pattern
    # that matches an import of the given library name.
    IMPORT_PATTERNS = {
        Language.PYTHON: [
            # import lib  /  import lib as x  /  import lib.sub
            r'^\s*import\s+{lib}\b',
            # from lib import ...  /  from lib.sub import ...
            r'^\s*from\s+{lib}\b',
        ],
        Language.JAVA: [
            # import pkg.Class;  /  import static pkg.Class.method;
            r'^\s*import\s+(?:static\s+)?{lib}\b',
        ],
        Language.NODE: [
            # require('lib')  /  require("lib")
            r"\brequire\s*\(\s*['\"]{{lib}}['\"]\s*\)",
            # import ... from 'lib'  /  import 'lib'
            r'^\s*import\s+.*?[\'"]{{lib}}[\'"]',
        ],
        Language.CPP: [
            # #include <lib>  /  #include <lib/header.h>  /  #include "lib..."
            r'^\s*#\s*include\s*[<"]{lib}[/\.>"]',
        ],
        Language.C: [
            r'^\s*#\s*include\s*[<"]{lib}[/\.>"]',
        ],
    }

    @property
    def name(self):
        return "forbidden_import"

    @property
    def description(self):
        return t("static_analysis.forbidden_import.description")

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription(
                "forbidden_imports",
                t("static_analysis.forbidden_import.params.libraries"),
                "list of strings"
            ),
            ParamDescription(
                "submission_language",
                t("static_analysis.forbidden_import.params.language"),
                "string or Language enum"
            ),
        ]

    def _build_patterns(self, library: str, language: Language) -> List[re.Pattern]:
        templates = self.IMPORT_PATTERNS.get(language, [])
        compiled: List[re.Pattern] = []
        escaped_library = re.escape(library)
        for tmpl in templates:
            raw = tmpl.replace('{{lib}}', escaped_library).replace('{lib}', escaped_library)
            compiled.append(re.compile(raw, re.MULTILINE))
        return compiled

    def _scan_file(self, content: str, forbidden: List[str],
                   language: Language) -> List[str]:
        violations: List[str] = []
        for lib in forbidden:
            patterns = self._build_patterns(lib, language)
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    violations.append(lib)
                    break
        return violations

    @staticmethod
    def _resolve_language(submission_language=None) -> Optional[Language]:
        if submission_language is None:
            return None
        if isinstance(submission_language, Language):
            return submission_language
        for lang in Language:
            if lang.value == str(submission_language).lower():
                return lang
        return None

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer],
                *args, forbidden_imports: List[str] = None,
                submission_language=None, **kwargs) -> TestResult:
        locale = kwargs.get("locale")
        if not forbidden_imports:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_import.report.no_imports", locale=locale)
            )

        language = self._resolve_language(submission_language)

        if language is None:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_import.report.no_lang", locale=locale)
            )

        if not files:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_import.report.no_files", locale=locale)
            )

        all_violations: List[str] = []
        for submission_file in files:
            found = self._scan_file(
                submission_file.content, forbidden_imports, language
            )
            for lib in found:
                all_violations.append(
                    t("static_analysis.forbidden_import.report.violation", locale=locale, lib=lib, file=submission_file.filename)
                )

        if all_violations:
            details = "\n".join(all_violations)
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_import.report.failure", locale=locale, details=details)
            )

        return TestResult(
            test_name=self.name,
            score=100.0,
            report=t("static_analysis.forbidden_import.report.success", locale=locale)
        )


# ===============================================================
# TestFunction for Forbidden Keyword/Construct Detection
# ===============================================================

class ForbiddenKeywordConfig(BaseModel):
    forbidden_keywords: List[str] = Field(default_factory=list)
    custom_ast_grep_rules: List[Dict[str, Any]] = Field(default_factory=list)

class ForbiddenKeywordTest(TestFunction):
    """
    Tests that a submission does NOT use any of the specified forbidden
    keywords or language constructs.
    """

    PREDEFINED_RULES: Dict[Language, Dict[str, Dict[str, Any]]] = {
        Language.PYTHON: {
            "for_loop": {"kind": "for_statement"},
            "while_loop": {"kind": "while_statement"},
            "eval_call": {"pattern": "eval($$$)"},
            "exec_call": {"pattern": "exec($$$)"},
        },
        Language.JAVA: {
            "for_loop": {"kind": "for_statement"},
            "while_loop": {"kind": "while_statement"},
        },
        Language.NODE: {
            "for_loop": {"kind": "for_statement"},
            "while_loop": {"kind": "while_statement"},
            "eval_call": {"pattern": "eval($$$)"},
        },
        Language.CPP: {
            "for_loop": {"kind": "for_statement"},
            "while_loop": {"kind": "while_statement"},
            "do_while_loop": {"kind": "do_statement"},
        },
        Language.C: {
            "for_loop": {"kind": "for_statement"},
            "while_loop": {"kind": "while_statement"},
            "do_while_loop": {"kind": "do_statement"},
        },
    }

    @property
    def name(self):
        return "forbidden_keyword"

    @property
    def description(self):
        return t("static_analysis.forbidden_keyword.description")

    @property
    def parameter_description(self):
        return [
            ParamDescription("forbidden_keywords", t("static_analysis.forbidden_keyword.params.keywords"), "list of strings"),
            ParamDescription("custom_ast_grep_rules", t("static_analysis.forbidden_keyword.params.custom_rules"), "list of dicts"),
        ]

    @property
    def config_schema(self) -> Type[BaseModel]:
        return ForbiddenKeywordConfig

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer],
                *args, forbidden_keywords: List[str] = None,
                custom_ast_grep_rules: List[Dict[str, Any]] = None,
                structural_analysis: Optional[StructuralAnalysisResult] = None,
                submission_language: Optional[Language] = None,
                **kwargs) -> TestResult:
        locale = kwargs.get("locale")
        forbidden_keywords = forbidden_keywords or []
        custom_ast_grep_rules = custom_ast_grep_rules or []

        if not forbidden_keywords and not custom_ast_grep_rules:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_keyword.report.no_rules", locale=locale)
            )

        if structural_analysis is None or not structural_analysis.available:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_keyword.report.no_analysis", locale=locale)
            )

        if submission_language is None:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_keyword.report.no_lang", locale=locale)
            )

        active_rules: List[Dict[str, Any]] = list(custom_ast_grep_rules)
        lang_predefined = self.PREDEFINED_RULES.get(submission_language, {})
        
        for kw in forbidden_keywords:
            if kw in lang_predefined:
                active_rules.append(lang_predefined[kw])

        if not active_rules:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_keyword.report.success", locale=locale)
            )

        all_violations: List[str] = []
        
        if not files:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_keyword.report.no_files", locale=locale)
            )

        if not structural_analysis.roots:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_keyword.report.no_analysis", locale=locale)
            )

        missing_roots = [
            sub_file.filename
            for sub_file in files
            if sub_file.filename not in structural_analysis.roots
            or structural_analysis.roots[sub_file.filename] is None
        ]
        if missing_roots:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_keyword.report.no_analysis", locale=locale)
            )

        for sub_file in files:
            root = structural_analysis.roots.get(sub_file.filename)
            if root is None:
                continue

            for rule in active_rules:
                matches = root.root().find_all(**rule)
                if matches:
                    rule_desc = rule.get("kind") or rule.get("pattern") or str(rule)
                    all_violations.append(
                        t("static_analysis.forbidden_keyword.report.violation", 
                          locale=locale, 
                          rule=rule_desc, 
                          file=sub_file.filename)
                    )

        if all_violations:
            details = "\n".join(all_violations)
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("static_analysis.forbidden_keyword.report.failure", locale=locale, details=details)
            )

        return TestResult(
            test_name=self.name,
            score=100.0,
            report=t("static_analysis.forbidden_keyword.report.success", locale=locale)
        )


class AiAlgorithmConfig(BaseModel):
    algorithm_name: str = Field(..., min_length=1)


class AiAlgorithmTestBase(AiTestFunction):
    algorithm_family: str = ""
    test_name: str = ""

    @property
    def name(self) -> str:
        return self.test_name

    @property
    def description(self) -> str:
        return t(f"static_analysis.{self.name}.description")

    @property
    def parameter_description(self) -> List[ParamDescription]:
        return [
            ParamDescription(
                "algorithm_name",
                t(f"static_analysis.{self.name}.params.algorithm_name"),
                "string",
            )
        ]

    @property
    def config_schema(self) -> Type[BaseModel]:
        return AiAlgorithmConfig

    def build_prompt(
        self,
        files: Optional[List[SubmissionFile]],
        **kwargs,
    ) -> str:
        algorithm_name = (kwargs.get("algorithm_name") or "").strip()
        file_names = ", ".join(f.filename for f in files) if files else ""

        if file_names:
            file_scope = f"Focus only on these files: {file_names}."
        else:
            file_scope = "No submission files were provided for this test."

        algo_label = algorithm_name or "Unknown algorithm"

        return (
            f"You are verifying a {self.algorithm_family} algorithm implementation.\n"
            f"Requested algorithm: {algo_label}.\n"
            f"{file_scope}\n\n"
            "Analyze the provided code and determine whether it is a correct and faithful "
            "implementation of the requested algorithm.\n"
            "Be strict: only accept if the algorithm is clearly implemented as specified.\n\n"
            "Criteria:\n"
            "1. The implementation must follow the specific logic and complexity "
            "characteristics of the requested algorithm.\n"
            "2. It must NOT be a wrapper around a built-in library function or standard "
            "library implementation.\n"
            "3. If it implements a different algorithm, it is incorrect.\n\n"
            "Scoring rules:\n"
            "- Score 100 only if the implementation is correct and faithful.\n"
            "- Otherwise score 0.\n\n"
            "In your feedback, briefly justify the decision and cite relevant code "
            "evidence. If the required algorithm is missing or there is no relevant "
            "code, score 0.\n"
            f"Use subject '{algo_label}'."
        )


class AiSortingAlgorithmTest(AiAlgorithmTestBase):
    algorithm_family = "sorting"
    test_name = "ai_sorting_algorithm"


class AiSearchAlgorithmTest(AiAlgorithmTestBase):
    algorithm_family = "search"
    test_name = "ai_search_algorithm"


class AiGraphAlgorithmTest(AiAlgorithmTestBase):
    algorithm_family = "graph"
    test_name = "ai_graph_algorithm"


class StaticAnalysisTemplate(Template):
    """
    A template for static analysis of code submissions.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "forbidden_import": ForbiddenImportTest(),
            "forbidden_keyword": ForbiddenKeywordTest(),
            "ai_sorting_algorithm": AiSortingAlgorithmTest(),
            "ai_search_algorithm": AiSearchAlgorithmTest(),
            "ai_graph_algorithm": AiGraphAlgorithmTest(),
        }

    @property
    def template_name(self):
        return t("static_analysis.template.name")

    @property
    def template_description(self):
        return t("static_analysis.template.description")

    @property
    def requires_sandbox(self) -> bool:
        # Static analysis tests usually don't require execution, 
        # but structural analysis (ast-grep) might need a sandbox in some future versions.
        # Currently, they run on the server side using the files content.
        return False

    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
