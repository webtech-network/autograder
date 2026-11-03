import logging
import re
from typing import Annotated, Any, Dict, Iterable, List, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field

from autograder.models.abstract.template import Template
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.test_function import EvaluationInput, ParameterIssue, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from autograder.models.language import Language
from autograder.models.evaluation_error import EvaluationError
from autograder.services.structural_analysis import RUNTIME_GRAMMARS, is_runtime_source, parse_source

# ===============================================================
# TestFunction for Forbidden Import Detection
# ===============================================================

class ForbiddenImportTest(TestFunction):
    """
    Tests that a submission does NOT import any of the specified forbidden libraries.

    Performs static analysis on submission file contents using language-aware
    regex patterns. Supports Python, Java, JavaScript/Node, C and C++.
    """

    minimum_files = 1

    def accepts_file(self, filename, language):
        """Only source files of the runtime language; documents never reach these rules."""
        return is_runtime_source(filename, language)

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
    supported_languages = [language.value for language in IMPORT_PATTERNS]

    @property
    def name(self):
        return "forbidden_import"

    @property
    def description(self):
        return t("static_analysis.forbidden_import.description")

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

    def execute(self, evaluation: EvaluationInput, *, forbidden_imports: Annotated[List[str], Field(
            default_factory=list, description=t("static_analysis.forbidden_import.params.libraries"))]) -> TestResult:
        locale = evaluation.locale
        files = evaluation.files
        if not forbidden_imports:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_import.report.no_imports", locale=locale)
            )

        language = evaluation.language

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

AST_RULE_KEYS = frozenset({'kind', 'pattern', 'regex', 'all', 'any', 'not', 'has', 'inside', 'precedes', 'follows'})


class ForbiddenKeywordConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    forbidden_keywords: List[str] = Field(
        default_factory=list, description=t("static_analysis.forbidden_keyword.params.keywords"))
    custom_ast_grep_rules: List[Dict[str, Any]] = Field(
        default_factory=list, description=t("static_analysis.forbidden_keyword.params.custom_rules"))

class ForbiddenKeywordTest(TestFunction):
    """
    Tests that a submission does NOT use any of the specified forbidden
    keywords or language constructs.
    """

    minimum_files = 1

    def accepts_file(self, filename, language):
        """Only source files of the runtime language; documents never reach these rules."""
        return is_runtime_source(filename, language)

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
    supported_languages = [language.value for language in PREDEFINED_RULES]
    required_capabilities = ("structural_analysis",)

    @property
    def name(self):
        return "forbidden_keyword"

    @property
    def description(self):
        return t("static_analysis.forbidden_keyword.description")

    @property
    def config_schema(self) -> Type[BaseModel]:
        return ForbiddenKeywordConfig

    def validate_parameters(self, parameters: Dict[str, Any], *,
                            languages: Tuple[str, ...]) -> Iterable[ParameterIssue]:
        """Keywords and custom rules must work for every allowed language."""
        for index, keyword in enumerate(parameters['forbidden_keywords']):
            if any(keyword not in self.PREDEFINED_RULES.get(Language(language), {}) for language in languages):
                yield ParameterIssue('UNSUPPORTED_KEYWORD', ('forbidden_keywords', index),
                                     'Keyword must be supported for every allowed language')
        for index, rule in enumerate(parameters['custom_ast_grep_rules']):
            if not rule or not set(rule).issubset(AST_RULE_KEYS):
                yield ParameterIssue('INVALID_AST_RULE', ('custom_ast_grep_rules', index), 'Expected an ast-grep rule object')
                continue
            try:
                from ast_grep_py import SgRoot  # pylint: disable=import-outside-toplevel
                for language in languages:
                    SgRoot('', RUNTIME_GRAMMARS[Language(language)]).root().find_all(**rule)
            except Exception:  # pylint: disable=broad-exception-caught
                yield ParameterIssue('INVALID_AST_RULE', ('custom_ast_grep_rules', index),
                                     'Rule must compile for every allowed language')

    def execute(self, evaluation: EvaluationInput, *, forbidden_keywords: List[str],
                custom_ast_grep_rules: List[Dict[str, Any]]) -> TestResult:
        locale = evaluation.locale
        files = evaluation.files
        submission_language = evaluation.language

        if not forbidden_keywords and not custom_ast_grep_rules:
            return TestResult(
                test_name=self.name,
                score=100.0,
                report=t("static_analysis.forbidden_keyword.report.no_rules", locale=locale)
            )

        if submission_language is None:
            raise EvaluationError("LANGUAGE_REQUIRED", "A language is required for structural assessment.", "submission")

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

        for sub_file in files:
            root = parse_source(sub_file, submission_language)

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
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    algorithm_name: str = Field(..., min_length=1, description="Name of the algorithm the submission must implement.")


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
    def config_schema(self) -> Type[BaseModel]:
        return AiAlgorithmConfig

    def build_prompt(self, evaluation: EvaluationInput, *, algorithm_name: str) -> str:
        files = evaluation.files
        algorithm_name = algorithm_name.strip()
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

