"""Tests for ForbiddenImportTest."""

from autograder.template_library.input_output import ForbiddenImportTest, InputOutputTemplate
from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.models.sandbox_models import Language


class TestForbiddenImportRegistration:
    """Test that ForbiddenImportTest is properly registered in the template."""

    def test_forbidden_import_registered_in_template(self):
        """Test that the forbidden_import test is available in InputOutputTemplate."""
        template = InputOutputTemplate()
        test = template.get_test("forbidden_import")
        assert test is not None
        assert test.name == "forbidden_import"


class TestForbiddenImportMetadata:
    """Test ForbiddenImportTest metadata and properties."""

    test_fn: ForbiddenImportTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()

    def test_name(self):
        """Test that the test name is 'forbidden_import'."""
        assert self.test_fn.name == "forbidden_import"

    def test_description_not_empty(self):
        """Test that the description is not empty."""
        assert len(self.test_fn.description) > 0

    def test_parameter_descriptions(self):
        """Test that the test has correct parameter descriptions."""
        params = self.test_fn.parameter_description
        assert len(params) == 2
        assert params[0].name == "forbidden_imports"
        assert params[1].name == "submission_language"

    def test_required_file_is_none(self):
        """Test that no specific file is required."""
        assert self.test_fn.required_file is None


class TestForbiddenImportEdgeCases:
    """Test edge cases for ForbiddenImportTest."""

    test_fn: ForbiddenImportTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()

    def test_none_forbidden_list(self):
        """Test that None forbidden_imports returns full score."""
        result = self.test_fn.execute([], None, forbidden_imports=None)
        assert result.score == 100.0

    def test_empty_forbidden_list(self):
        """Test that empty forbidden_imports list returns full score."""
        result = self.test_fn.execute([], None, forbidden_imports=[])
        assert result.score == 100.0

    def test_no_language_gives_zero(self):
        """Test that missing language returns score 0."""
        files = [SubmissionFile("main.py", "import os")]
        result = self.test_fn.execute(files, None, forbidden_imports=["os"])
        assert result.score == 0.0
        assert "language" in result.report.lower()

    def test_no_files_gives_full_score(self):
        """Test that empty file list returns full score."""
        result = self.test_fn.execute(
            [], None,
            forbidden_imports=["os"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 100.0

    def test_language_passed_as_string(self):
        """Test that language can be passed as a string."""
        files = [SubmissionFile("main.py", "import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language="python",
        )
        assert result.score == 0.0


class TestForbiddenImportPython:
    """Test ForbiddenImportTest with Python submissions."""

    test_fn: ForbiddenImportTest
    lang: Language

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()
        self.lang = Language.PYTHON

    def test_import_statement(self):
        """Test detection of 'import numpy'."""
        files = [SubmissionFile("main.py", "import numpy\nx = 1\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["numpy"],
            submission_language=self.lang,
        )
        assert result.score == 0.0
        assert "numpy" in result.report

    def test_import_as(self):
        """Test detection of 'import numpy as np'."""
        files = [SubmissionFile("main.py", "import numpy as np\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["numpy"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_from_import(self):
        """Test detection of 'from pandas import DataFrame'."""
        files = [SubmissionFile("main.py", "from pandas import DataFrame\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["pandas"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_from_submodule(self):
        """Test detection of 'from os.path import join'."""
        files = [SubmissionFile("main.py", "from os.path import join\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_from_deep_submodule(self):
        """Test detection of 'from os.path.posixpath import join'."""
        files = [SubmissionFile("main.py", "from os.path.posixpath import join\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_from_wildcard_import(self):
        """Test detection of 'from os import *'."""
        files = [SubmissionFile("main.py", "from os import *\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_from_multiline_parens(self):
        """Test detection of multiline 'from os import (path, getcwd)'."""
        files = [SubmissionFile("main.py", "from os import (\n    path,\n    getcwd,\n)\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_import_with_inline_comment(self):
        """Test detection of 'import os  # needed for path'."""
        files = [SubmissionFile("main.py", "import os  # needed for path\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_comma_imports(self):
        """Test detection of 'import os, sys'."""
        files = [SubmissionFile("main.py", "import os, sys\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_indented_import_inside_function(self):
        """Test detection of import inside a function body."""
        files = [SubmissionFile("main.py", "def foo():\n    import os\n    return os.getcwd()\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_allowed_import(self):
        """Test that an allowed import does not trigger detection."""
        files = [SubmissionFile("main.py", "import math\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["numpy"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_no_imports_at_all(self):
        """Test that code without imports passes."""
        files = [SubmissionFile("main.py", "x = 1 + 2\nprint(x)\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_partial_name_no_false_positive(self):
        """Test that 'os' does not match 'oscar'."""
        files = [SubmissionFile("main.py", "import oscar\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_commented_import_not_detected(self):
        """Test that a commented-out import is not detected."""
        files = [SubmissionFile("main.py", "# import os\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_import_in_string_literal_not_detected(self):
        """Test that 'import os' inside a string literal is not detected."""
        files = [SubmissionFile("main.py", "text = 'import os'\nprint(text)\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_multiple_forbidden_libraries(self):
        """Test detection of multiple forbidden libraries in a single file."""
        files = [SubmissionFile("main.py", "import os\nimport sys\nimport math\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os", "sys"],
            submission_language=self.lang,
        )
        assert result.score == 0.0
        assert "os" in result.report
        assert "sys" in result.report

    def test_violation_in_second_file(self):
        """Test that a violation in the second file is detected."""
        files = [
            SubmissionFile("main.py", "print('hi')\n"),
            SubmissionFile("helpers.py", "import os\n"),
        ]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0
        assert "helpers.py" in result.report

    def test_dirty_file_among_clean(self):
        """Test that a single dirty file among clean ones triggers detection."""
        files = [
            SubmissionFile("clean.py", "x = 1\n"),
            SubmissionFile("dirty.py", "import os\n"),
            SubmissionFile("also_clean.py", "y = 2\n"),
        ]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=self.lang,
        )
        assert result.score == 0.0
        assert "dirty.py" in result.report

    def test_all_files_clean(self):
        """Test that all clean files return full score."""
        files = [
            SubmissionFile("a.py", "import math\n"),
            SubmissionFile("b.py", "import json\n"),
        ]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os", "subprocess"],
            submission_language=self.lang,
        )
        assert result.score == 100.0


class TestForbiddenImportJava:
    """Test ForbiddenImportTest with Java submissions."""

    test_fn: ForbiddenImportTest
    lang: Language

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()
        self.lang = Language.JAVA

    def test_basic_import(self):
        """Test detection of 'import java.util.Scanner'."""
        files = [SubmissionFile("Main.java", "import java.util.Scanner;\npublic class Main {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["java.util.Scanner"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_static_import(self):
        """Test detection of 'import static java.lang.Math.PI'."""
        files = [SubmissionFile("Main.java", "import static java.lang.Math.PI;\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["java.lang.Math"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_wildcard_import(self):
        """Test detection of 'import java.util.*'."""
        files = [SubmissionFile("Main.java", "import java.util.*;\npublic class Main {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["java.util"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_allowed_import(self):
        """Test that an allowed import does not trigger detection."""
        files = [SubmissionFile("Main.java", "import java.util.List;\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["java.io.File"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_commented_import_not_detected(self):
        """Test that a commented-out import is not detected."""
        files = [SubmissionFile("Main.java", "// import java.util.Scanner;\npublic class Main {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["java.util.Scanner"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_multiple_forbidden_all_reported(self):
        """Test that multiple forbidden imports are all reported."""
        files = [SubmissionFile("Main.java", "import java.io.File;\nimport java.net.Socket;\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["java.io.File", "java.net.Socket"],
            submission_language=self.lang,
        )
        assert result.score == 0.0
        assert "java.io.File" in result.report
        assert "java.net.Socket" in result.report


class TestForbiddenImportNode:
    """Test ForbiddenImportTest with JavaScript/Node submissions."""

    test_fn: ForbiddenImportTest
    lang: Language

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()
        self.lang = Language.NODE

    def test_require_single_quotes(self):
        """Test detection of require('fs')."""
        files = [SubmissionFile("index.js", "const fs = require('fs');\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_require_double_quotes(self):
        """Test detection of require("fs")."""
        files = [SubmissionFile("index.js", 'const fs = require("fs");\n')]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_require_with_destructuring(self):
        """Test detection of const { readFile } = require('fs')."""
        files = [SubmissionFile("index.js", "const { readFile } = require('fs');\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_es_default_import(self):
        """Test detection of import express from 'express'."""
        files = [SubmissionFile("index.js", "import express from 'express';\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["express"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_es_named_import(self):
        """Test detection of import { readFile } from 'fs'."""
        files = [SubmissionFile("index.js", "import { readFile } from 'fs';\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_es_star_import(self):
        """Test detection of import * as express from 'express'."""
        files = [SubmissionFile("index.js", "import * as express from 'express';\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["express"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_allowed_require(self):
        """Test that an allowed require does not trigger detection."""
        files = [SubmissionFile("index.js", "const path = require('path');\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_partial_module_name_no_false_positive(self):
        """Test that 'fs' does not match 'fs-extra'."""
        files = [SubmissionFile("index.js", "const fse = require('fs-extra');\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_commented_require_still_detected(self):
        """Test that a commented require is still detected (known limitation).

        The require() regex uses \\b (not ^) so a JS line-comment
        does NOT prevent matching.
        """
        files = [SubmissionFile("index.js", "// const fs = require('fs');\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["fs"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_multiple_files(self):
        """Test detection across multiple files."""
        files = [
            SubmissionFile("app.js", "const http = require('http');\n"),
            SubmissionFile("utils.js", "const path = require('path');\n"),
        ]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["http"],
            submission_language=self.lang,
        )
        assert result.score == 0.0
        assert "app.js" in result.report


class TestForbiddenImportCpp:
    """Test ForbiddenImportTest with C++ submissions."""

    test_fn: ForbiddenImportTest
    lang: Language

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()
        self.lang = Language.CPP

    def test_angle_bracket_include(self):
        """Test detection of #include <thread>."""
        files = [SubmissionFile("main.cpp", "#include <thread>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["thread"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_quoted_include(self):
        """Test detection of #include "mylib.h"."""
        files = [SubmissionFile("main.cpp", '#include "mylib.h"\nint main() {}\n')]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["mylib"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_include_with_path(self):
        """Test detection of #include <boost/algorithm/string.hpp>."""
        files = [SubmissionFile("main.cpp", "#include <boost/algorithm/string.hpp>\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["boost"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_include_with_header_extension(self):
        """Test detection of #include <pthread.h>."""
        files = [SubmissionFile("main.cpp", "#include <pthread.h>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["pthread"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_include_with_spaces(self):
        """Test detection of '#  include  <thread>' with extra spaces."""
        files = [SubmissionFile("main.cpp", "#  include  <thread>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["thread"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_allowed_include(self):
        """Test that an allowed include does not trigger detection."""
        files = [SubmissionFile("main.cpp", "#include <iostream>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["thread"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_commented_include_not_detected(self):
        """Test that a commented-out include is not detected."""
        files = [SubmissionFile("main.cpp", "// #include <thread>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["thread"],
            submission_language=self.lang,
        )
        assert result.score == 100.0

    def test_multiple_includes_one_forbidden(self):
        """Test that only the forbidden include is caught among several."""
        files = [SubmissionFile("main.cpp", "#include <iostream>\n#include <thread>\n#include <vector>\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["thread"],
            submission_language=self.lang,
        )
        assert result.score == 0.0


class TestForbiddenImportC:
    """Test ForbiddenImportTest with C submissions."""

    test_fn: ForbiddenImportTest
    lang: Language

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()
        self.lang = Language.C

    def test_forbidden_header(self):
        """Test detection of #include <pthread.h> in C."""
        files = [SubmissionFile("main.c", "#include <pthread.h>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["pthread"],
            submission_language=self.lang,
        )
        assert result.score == 0.0

    def test_allowed_header(self):
        """Test that an allowed header does not trigger detection."""
        files = [SubmissionFile("main.c", "#include <stdio.h>\nint main() {}\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["pthread"],
            submission_language=self.lang,
        )
        assert result.score == 100.0


class TestForbiddenImportReport:
    """Test report content from ForbiddenImportTest."""

    test_fn: ForbiddenImportTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()

    def test_clean_report_has_message(self):
        """Test that a clean result has a non-empty report."""
        files = [SubmissionFile("main.py", "x = 1\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 100.0
        assert len(result.report) > 0

    def test_violation_lists_library_and_file(self):
        """Test that a violation report lists the library and filename."""
        files = [SubmissionFile("app.py", "import subprocess\n")]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["subprocess"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 0.0
        assert "subprocess" in result.report
        assert "app.py" in result.report

    def test_no_forbidden_list_report(self):
        """Test that the report mentions nothing to check when list is None."""
        result = self.test_fn.execute([], None, forbidden_imports=None)
        assert "nothing to check" in result.report.lower() or "no forbidden" in result.report.lower()

    def test_no_files_report(self):
        """Test that the report for no files returns full score."""
        result = self.test_fn.execute(
            [], None,
            forbidden_imports=["os"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 100.0

    def test_multiple_violations_all_listed(self):
        """Test that all violations across files are listed in the report."""
        files = [
            SubmissionFile("a.py", "import os\n"),
            SubmissionFile("b.py", "import sys\n"),
        ]
        result = self.test_fn.execute(
            files, None,
            forbidden_imports=["os", "sys"],
            submission_language=Language.PYTHON,
        )
        assert result.score == 0.0
        for token in ("os", "sys", "a.py", "b.py"):
            assert token in result.report


class TestForbiddenImportHelpers:
    """Test internal helper methods of ForbiddenImportTest."""

    test_fn: ForbiddenImportTest

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fn = ForbiddenImportTest()

    def _resolve_language(self, *args, **kwargs):
        return getattr(self.test_fn, "_resolve_language")(*args, **kwargs)

    def _build_patterns(self, *args, **kwargs):
        return getattr(self.test_fn, "_build_patterns")(*args, **kwargs)

    def _scan_file(self, *args, **kwargs):
        return getattr(self.test_fn, "_scan_file")(*args, **kwargs)

    def test_resolve_language_none(self):
        """Test that None input returns None."""
        assert self._resolve_language(None) is None

    def test_resolve_language_enum(self):
        """Test that a Language enum is returned as-is."""
        assert self._resolve_language(Language.PYTHON) == Language.PYTHON

    def test_resolve_language_valid_string(self):
        """Test that a valid lowercase string resolves correctly."""
        assert self._resolve_language("python") == Language.PYTHON

    def test_resolve_language_invalid_string(self):
        """Test that an unsupported language string returns None."""
        assert self._resolve_language("cobol") is None

    def test_resolve_language_uppercase_string(self):
        """Test behaviour with uppercase string (enum values are lowercase)."""
        result = self._resolve_language("Python")
        assert result is None or result == Language.PYTHON

    def test_build_patterns_returns_non_empty_list(self):
        """Test that _build_patterns returns a non-empty list for a known language."""
        patterns = self._build_patterns("os", Language.PYTHON)
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_build_patterns_unknown_language_returns_empty(self):
        """Test that _build_patterns returns empty list for unknown language."""
        assert not self._build_patterns("os", "unknown_lang")

    def test_scan_file_no_violations(self):
        """Test that _scan_file returns empty list when no violations exist."""
        violations = self._scan_file("x = 1\n", ["os"], Language.PYTHON)
        assert not violations

    def test_scan_file_with_violation(self):
        """Test that _scan_file detects a forbidden import."""
        violations = self._scan_file("import os\n", ["os"], Language.PYTHON)
        assert "os" in violations

    def test_scan_file_deduplicates_per_library(self):
        """Test that _scan_file reports each library at most once."""
        violations = self._scan_file("import os\nfrom os import path\n", ["os"], Language.PYTHON)
        assert violations.count("os") == 1
