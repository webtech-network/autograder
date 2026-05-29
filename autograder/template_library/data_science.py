
import csv
import io
import json
import logging
import re
from typing import Optional

from autograder.models.abstract.template import Template
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.template_library.execution_base import BaseExecutionTest
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer


class ExpectStdoutValueTest(BaseExecutionTest):
    """
    Runs a command, extracts a value from stdout via regex
    (using a named group 'value'), and compares it to an expected
    value with optional numeric tolerance.
    """

    @property
    def name(self):
        return "expect_stdout_value"

    @property
    def description(self):
        return t("data_science.expect_stdout_value.description")

    @property
    def required_file(self):
        """No specific file is required before execution."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("program_command", t("data_science.expect_stdout_value.params.program_command"), "string"),
            ParamDescription("extraction_pattern", t("data_science.expect_stdout_value.params.extraction_pattern"), "string"),
            ParamDescription("expected_value", t("data_science.expect_stdout_value.params.expected_value"), "number"),
            ParamDescription("tolerance", t("data_science.expect_stdout_value.params.tolerance"), "number"),
        ]

    # pylint: disable=too-many-locals
    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        program_command = kwargs.get("program_command")
        extraction_pattern = kwargs.get("extraction_pattern", "")
        expected_value = kwargs.get("expected_value")
        tolerance = kwargs.get("tolerance", 0)
        locale = kwargs.get("locale")

        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                program_command=program_command,
            )

            error_result = self.check_for_base_errors(output, locale=locale)
            if error_result:
                return error_result

            stdout = output.stdout.strip()

            # Extract value using regex with named group 'value'
            match = re.search(extraction_pattern, stdout)
            if not match or "value" not in match.groupdict():
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=t("data_science.expect_stdout_value.report.no_match",
                             locale=locale, pattern=extraction_pattern, stdout=stdout)
                )

            actual_str = match.group("value")
            try:
                actual_value = float(actual_str)
            except (ValueError, TypeError):
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=t("data_science.expect_stdout_value.report.not_numeric",
                             locale=locale, value=actual_str)
                )

            expected_float = float(expected_value)
            tol = float(tolerance)

            if abs(actual_value - expected_float) <= tol:
                return TestResult(
                    test_name=self.name,
                    score=100.0,
                    report=t("data_science.expect_stdout_value.report.success",
                             locale=locale, expected=expected_float, actual=actual_value, tolerance=tol)
                )

            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("data_science.expect_stdout_value.report.failure",
                         locale=locale, expected=expected_float, actual=actual_value, tolerance=tol)
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("data_science.expect_stdout_value.report.internal_error",
                         locale=locale, error=str(e))
            )


class ExpectMetricTest(BaseExecutionTest):
    """
    Runs a command, extracts a numeric metric from stdout via regex,
    and validates it against a threshold using a comparison operator.

    Designed for ML metrics like accuracy, RMSE, F1-score, etc.
    """

    VALID_CONDITIONS = {">=", "<=", ">", "<", "=="}

    @property
    def name(self):
        return "expect_metric"

    @property
    def description(self):
        return t("data_science.expect_metric.description")

    @property
    def required_file(self):
        """No specific file is required before execution."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("program_command", t("data_science.expect_metric.params.program_command"), "string"),
            ParamDescription("metric_pattern", t("data_science.expect_metric.params.metric_pattern"), "string"),
            ParamDescription("condition", t("data_science.expect_metric.params.condition"), "string"),
            ParamDescription("threshold", t("data_science.expect_metric.params.threshold"), "number"),
        ]

    @staticmethod
    def _evaluate_condition(actual: float, condition: str, threshold: float) -> bool:
        """Evaluate a comparison condition between actual and threshold."""
        if condition == ">=":
            return actual >= threshold
        if condition == "<=":
            return actual <= threshold
        if condition == ">":
            return actual > threshold
        if condition == "<":
            return actual < threshold
        if condition == "==":
            return actual == threshold
        return False

    # pylint: disable=too-many-locals,too-many-return-statements
    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        program_command = kwargs.get("program_command")
        metric_pattern = kwargs.get("metric_pattern", "")
        condition = kwargs.get("condition", ">=")
        threshold = kwargs.get("threshold")
        locale = kwargs.get("locale")

        # Validate condition operator
        if condition not in self.VALID_CONDITIONS:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("data_science.expect_metric.report.invalid_condition",
                         locale=locale, condition=condition,
                         valid=", ".join(sorted(self.VALID_CONDITIONS)))
            )

        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                program_command=program_command,
            )

            error_result = self.check_for_base_errors(output, locale=locale)
            if error_result:
                return error_result

            stdout = output.stdout.strip()

            # Extract metric using regex with named group 'value'
            match = re.search(metric_pattern, stdout)
            if not match or "value" not in match.groupdict():
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=t("data_science.expect_metric.report.no_match",
                             locale=locale, pattern=metric_pattern, stdout=stdout)
                )

            actual_str = match.group("value")
            try:
                actual_value = float(actual_str)
            except (ValueError, TypeError):
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=t("data_science.expect_metric.report.not_numeric",
                             locale=locale, value=actual_str)
                )

            threshold_float = float(threshold)

            if self._evaluate_condition(actual_value, condition, threshold_float):
                return TestResult(
                    test_name=self.name,
                    score=100.0,
                    report=t("data_science.expect_metric.report.success",
                             locale=locale, metric=actual_value,
                             condition=condition, threshold=threshold_float)
                )

            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("data_science.expect_metric.report.failure",
                         locale=locale, metric=actual_value,
                         condition=condition, threshold=threshold_float)
            )

        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("data_science.expect_metric.report.internal_error",
                         locale=locale, error=str(e))
            )


class ExpectCsvOutputTest(BaseExecutionTest):
    """
    Runs a command, extracts a CSV file from the sandbox, and validates:
    - Column names (presence and order)
    - Shape (rows x cols)
    - Cell values with numeric tolerance

    Scoring is proportional: each check contributes to the final score.
    """

    @property
    def name(self):
        return "expect_csv_output"

    @property
    def description(self):
        return t("data_science.expect_csv_output.description")

    @property
    def required_file(self):
        """No specific file is required before execution."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("program_command", t("data_science.expect_csv_output.params.program_command"), "string"),
            ParamDescription("artifact_path", t("data_science.expect_csv_output.params.artifact_path"), "string"),
            ParamDescription("expected_columns", t("data_science.expect_csv_output.params.expected_columns"), "list of strings"),
            ParamDescription("expected_shape", t("data_science.expect_csv_output.params.expected_shape"), "list [rows, cols]"),
            ParamDescription("tolerance", t("data_science.expect_csv_output.params.tolerance"), "number"),
            ParamDescription("expected_values", t("data_science.expect_csv_output.params.expected_values"), "list of lists"),
        ]

    @staticmethod
    def _validate_artifact_path(artifact_path: str) -> Optional[str]:
        """Return an error message if the path is unsafe, else None."""
        if not artifact_path:
            return "artifact_path is required"
        if artifact_path.startswith("/") or ".." in artifact_path.split("/"):
            return f"Invalid artifact_path (absolute or traversal): {artifact_path}"
        return None

    @staticmethod
    def _parse_csv(content: str) -> tuple:
        """Parse CSV content, return (headers, rows) or raise ValueError."""
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            raise ValueError("CSV file is empty")
        headers = rows[0]
        data_rows = rows[1:]
        return headers, data_rows

    @staticmethod
    def _values_match(actual: str, expected, tolerance: float) -> bool:
        """Compare two values with numeric tolerance if both are numbers."""
        try:
            actual_num = float(actual)
            expected_num = float(expected)
            return abs(actual_num - expected_num) <= tolerance
        except (ValueError, TypeError):
            return str(actual).strip() == str(expected).strip()

    # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        program_command = kwargs.get("program_command")
        artifact_path = kwargs.get("artifact_path", "")
        expected_columns = kwargs.get("expected_columns")
        expected_shape = kwargs.get("expected_shape")
        tolerance = float(kwargs.get("tolerance", 0))
        expected_values = kwargs.get("expected_values")
        locale = kwargs.get("locale")

        # Validate artifact path
        path_error = self._validate_artifact_path(artifact_path)
        if path_error:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_csv_output.report.invalid_path",
                         locale=locale, error=path_error)
            )

        # Execute program
        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                program_command=program_command,
            )
            error_result = self.check_for_base_errors(output, locale=locale)
            if error_result:
                return error_result
        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_csv_output.report.internal_error",
                         locale=locale, error=str(e))
            )

        # Extract file
        try:
            extracted = sandbox.extract_file(f"/app/{artifact_path}")
        except FileNotFoundError:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_csv_output.report.file_not_found",
                         locale=locale, path=artifact_path)
            )
        except (ValueError, RuntimeError) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_csv_output.report.extraction_error",
                         locale=locale, error=str(e))
            )

        # Parse CSV
        try:
            headers, data_rows = self._parse_csv(extracted.content_text)
        except (ValueError, csv.Error) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_csv_output.report.parse_error",
                         locale=locale, error=str(e))
            )

        # Proportional scoring: each active check contributes equally
        checks = []
        details = []

        # Check columns
        if expected_columns is not None:
            columns_match = headers == expected_columns
            checks.append(columns_match)
            if columns_match:
                details.append(t("data_science.expect_csv_output.report.columns_ok", locale=locale))
            else:
                details.append(t("data_science.expect_csv_output.report.columns_mismatch",
                                 locale=locale, expected=expected_columns, actual=headers))

        # Check shape
        if expected_shape is not None:
            expected_rows, expected_cols = expected_shape
            actual_rows = len(data_rows)
            actual_cols = len(headers)
            shape_match = (actual_rows == expected_rows and actual_cols == expected_cols)
            checks.append(shape_match)
            if shape_match:
                details.append(t("data_science.expect_csv_output.report.shape_ok",
                                 locale=locale, rows=actual_rows, cols=actual_cols))
            else:
                details.append(t("data_science.expect_csv_output.report.shape_mismatch",
                                 locale=locale,
                                 expected_rows=expected_rows, expected_cols=expected_cols,
                                 actual_rows=actual_rows, actual_cols=actual_cols))

        # Check values with tolerance
        if expected_values is not None:
            total_cells = 0
            matching_cells = 0
            for row_idx, expected_row in enumerate(expected_values):
                if row_idx >= len(data_rows):
                    total_cells += len(expected_row)
                    continue
                actual_row = data_rows[row_idx]
                for col_idx, expected_val in enumerate(expected_row):
                    total_cells += 1
                    if col_idx < len(actual_row):
                        if self._values_match(actual_row[col_idx], expected_val, tolerance):
                            matching_cells += 1

            if total_cells > 0:
                value_ratio = matching_cells / total_cells
                checks.append(value_ratio)
                details.append(t("data_science.expect_csv_output.report.values_check",
                                 locale=locale, matching=matching_cells,
                                 total=total_cells, ratio=f"{value_ratio:.0%}"))
            else:
                checks.append(True)

        # Calculate final score
        if not checks:
            # No checks specified — file exists, that's a pass
            return TestResult(
                test_name=self.name, score=100.0,
                report=t("data_science.expect_csv_output.report.success",
                         locale=locale, path=artifact_path)
            )

        # Proportional: bool checks count as 1.0/0.0, ratio checks as their value
        score_parts = []
        for check in checks:
            if isinstance(check, bool):
                score_parts.append(100.0 if check else 0.0)
            else:
                score_parts.append(float(check) * 100.0)

        final_score = sum(score_parts) / len(score_parts)
        report = "\n".join(details)

        if final_score >= 100.0:
            report = t("data_science.expect_csv_output.report.success",
                        locale=locale, path=artifact_path) + "\n" + report

        return TestResult(
            test_name=self.name,
            score=round(final_score, 2),
            report=report
        )


class ExpectJsonOutputTest(BaseExecutionTest):
    """
    Runs a command, extracts a JSON file from the sandbox, and validates:
    - Required keys exist
    - Value equality (with tolerance for numeric values)
    - Nested key access via dot notation (e.g., "metrics.accuracy")
    """

    @property
    def name(self):
        return "expect_json_output"

    @property
    def description(self):
        return t("data_science.expect_json_output.description")

    @property
    def required_file(self):
        """No specific file is required before execution."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("program_command", t("data_science.expect_json_output.params.program_command"), "string"),
            ParamDescription("artifact_path", t("data_science.expect_json_output.params.artifact_path"), "string"),
            ParamDescription("required_keys", t("data_science.expect_json_output.params.required_keys"), "list of strings"),
            ParamDescription("expected_values", t("data_science.expect_json_output.params.expected_values"), "dict"),
            ParamDescription("tolerance", t("data_science.expect_json_output.params.tolerance"), "number"),
        ]

    @staticmethod
    def _validate_artifact_path(artifact_path: str) -> Optional[str]:
        """Return an error message if the path is unsafe, else None."""
        if not artifact_path:
            return "artifact_path is required"
        if artifact_path.startswith("/") or ".." in artifact_path.split("/"):
            return f"Invalid artifact_path (absolute or traversal): {artifact_path}"
        return None

    @staticmethod
    def _get_nested_value(data: dict, dotted_key: str):
        """
        Access a nested value using dot notation.
        Returns (value, True) if found, (None, False) if not.
        """
        keys = dotted_key.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None, False
        return current, True

    @staticmethod
    def _values_match(actual, expected, tolerance: float) -> bool:
        """Compare two values with numeric tolerance if both are numbers."""
        try:
            actual_num = float(actual)
            expected_num = float(expected)
            return abs(actual_num - expected_num) <= tolerance
        except (ValueError, TypeError):
            return actual == expected

    # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches
    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        program_command = kwargs.get("program_command")
        artifact_path = kwargs.get("artifact_path", "")
        required_keys = kwargs.get("required_keys")
        expected_values = kwargs.get("expected_values")
        tolerance = float(kwargs.get("tolerance", 0))
        locale = kwargs.get("locale")

        # Validate artifact path
        path_error = self._validate_artifact_path(artifact_path)
        if path_error:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_json_output.report.invalid_path",
                         locale=locale, error=path_error)
            )

        # Execute program
        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                program_command=program_command,
            )
            error_result = self.check_for_base_errors(output, locale=locale)
            if error_result:
                return error_result
        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_json_output.report.internal_error",
                         locale=locale, error=str(e))
            )

        # Extract file
        try:
            extracted = sandbox.extract_file(f"/app/{artifact_path}")
        except FileNotFoundError:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_json_output.report.file_not_found",
                         locale=locale, path=artifact_path)
            )
        except (ValueError, RuntimeError) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_json_output.report.extraction_error",
                         locale=locale, error=str(e))
            )

        # Parse JSON
        try:
            data = json.loads(extracted.content_text)
        except json.JSONDecodeError as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_json_output.report.parse_error",
                         locale=locale, error=str(e))
            )

        # Proportional scoring
        checks = []
        details = []

        # Check required keys
        if required_keys is not None:
            for key in required_keys:
                _, found = self._get_nested_value(data, key)
                checks.append(found)
                if found:
                    details.append(t("data_science.expect_json_output.report.key_found",
                                     locale=locale, field_key=key))
                else:
                    details.append(t("data_science.expect_json_output.report.key_missing",
                                     locale=locale, field_key=key))

        # Check expected values
        if expected_values is not None:
            for key, expected_val in expected_values.items():
                actual_val, found = self._get_nested_value(data, key)
                if not found:
                    checks.append(False)
                    details.append(t("data_science.expect_json_output.report.value_key_missing",
                                     locale=locale, field_key=key))
                elif self._values_match(actual_val, expected_val, tolerance):
                    checks.append(True)
                    details.append(t("data_science.expect_json_output.report.value_match",
                                     locale=locale, field_key=key, expected=expected_val, actual=actual_val))
                else:
                    checks.append(False)
                    details.append(t("data_science.expect_json_output.report.value_mismatch",
                                     locale=locale, field_key=key, expected=expected_val, actual=actual_val))

        # Calculate final score
        if not checks:
            return TestResult(
                test_name=self.name, score=100.0,
                report=t("data_science.expect_json_output.report.success",
                         locale=locale, path=artifact_path)
            )

        passed = sum(1 for c in checks if c)
        total = len(checks)
        final_score = (passed / total) * 100.0
        report = "\n".join(details)

        if final_score >= 100.0:
            report = t("data_science.expect_json_output.report.success",
                        locale=locale, path=artifact_path) + "\n" + report

        return TestResult(
            test_name=self.name,
            score=round(final_score, 2),
            report=report
        )


class ExpectModelArtifactTest(BaseExecutionTest):
    """
    Runs a command and verifies that a trained model file was produced
    in the sandbox with a minimum file size.
    """

    @property
    def name(self):
        return "expect_model_artifact"

    @property
    def description(self):
        return t("data_science.expect_model_artifact.description")

    @property
    def required_file(self):
        """No specific file is required before execution."""
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("program_command", t("data_science.expect_model_artifact.params.program_command"), "string"),
            ParamDescription("artifact_path", t("data_science.expect_model_artifact.params.artifact_path"), "string"),
            ParamDescription("min_size_bytes", t("data_science.expect_model_artifact.params.min_size_bytes"), "integer"),
        ]

    @staticmethod
    def _validate_artifact_path(artifact_path: str) -> Optional[str]:
        """Return an error message if the path is unsafe, else None."""
        if not artifact_path:
            return "artifact_path is required"
        if artifact_path.startswith("/") or ".." in artifact_path.split("/"):
            return f"Invalid artifact_path (absolute or traversal): {artifact_path}"
        return None

    # pylint: disable=too-many-return-statements
    def execute(self, files, sandbox: SandboxContainer, *args, **kwargs) -> TestResult:
        program_command = kwargs.get("program_command")
        artifact_path = kwargs.get("artifact_path", "")
        min_size_bytes = int(kwargs.get("min_size_bytes", 0))
        locale = kwargs.get("locale")

        # Validate artifact path
        path_error = self._validate_artifact_path(artifact_path)
        if path_error:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_model_artifact.report.invalid_path",
                         locale=locale, error=path_error)
            )

        # Execute program
        try:
            output = self.run_sandbox_execution(
                sandbox=sandbox,
                program_command=program_command,
            )
            error_result = self.check_for_base_errors(output, locale=locale)
            if error_result:
                return error_result
        except (ValueError, TimeoutError, RuntimeError) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_model_artifact.report.internal_error",
                         locale=locale, error=str(e))
            )

        # Extract file
        try:
            extracted = sandbox.extract_file(f"/app/{artifact_path}")
        except FileNotFoundError:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_model_artifact.report.file_not_found",
                         locale=locale, path=artifact_path)
            )
        except (ValueError, RuntimeError) as e:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_model_artifact.report.extraction_error",
                         locale=locale, error=str(e))
            )

        # Validate file size
        actual_size = extracted.size
        if actual_size < min_size_bytes:
            return TestResult(
                test_name=self.name, score=0.0,
                report=t("data_science.expect_model_artifact.report.too_small",
                         locale=locale, path=artifact_path,
                         min_size=min_size_bytes, actual_size=actual_size)
            )

        return TestResult(
            test_name=self.name, score=100.0,
            report=t("data_science.expect_model_artifact.report.success",
                     locale=locale, path=artifact_path, size=actual_size)
        )


class DataScienceTemplate(Template):
    """
    A template for data science assignments. Validates data manipulation
    results, model outputs, statistical metrics, and generated artifacts.

    Requires sandbox execution (requires_sandbox = True).
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "expect_stdout_value": ExpectStdoutValueTest(),
            "expect_metric": ExpectMetricTest(),
            "expect_csv_output": ExpectCsvOutputTest(),
            "expect_json_output": ExpectJsonOutputTest(),
            "expect_model_artifact": ExpectModelArtifactTest(),
        }

    @property
    def template_name(self):
        return t("data_science.template.name")

    @property
    def template_description(self):
        return t("data_science.template.description")

    @property
    def requires_sandbox(self) -> bool:
        return True

    def get_test(self, name: str):
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
