"""
Unit tests for DataScienceTemplate and its test functions.

Tests cover:
- ExpectStdoutValueTest: regex extraction, tolerance, no match, non-numeric, execution errors
- ExpectMetricTest: all condition operators, threshold pass/fail, no match, invalid condition
- ExpectCsvOutputTest: columns, shape, values with tolerance, proportional scoring, missing file
- ExpectJsonOutputTest: required keys, expected values, nested access, tolerance, missing file
- ExpectModelArtifactTest: file exists, min size pass/fail, missing file
- DataScienceTemplate: contract validation, test registration
"""

import json
import unittest
from unittest.mock import MagicMock

from autograder.template_library.data_science import (
    DataScienceTemplate,
    ExpectStdoutValueTest,
    ExpectMetricTest,
    ExpectCsvOutputTest,
    ExpectJsonOutputTest,
    ExpectModelArtifactTest,
)
from sandbox_manager.models.sandbox_models import (
    CommandResponse, ResponseCategory, ExtractedFile,
)


def _make_sandbox(stdout="", stderr="", exit_code=0, category=ResponseCategory.SUCCESS):
    """Return a mock sandbox whose run_commands returns the given CommandResponse."""
    sandbox = MagicMock()
    sandbox.run_commands.return_value = CommandResponse(
        stdout=stdout, stderr=stderr, exit_code=exit_code,
        execution_time=0.1, category=category,
    )
    sandbox.run_command.return_value = CommandResponse(
        stdout=stdout, stderr=stderr, exit_code=exit_code,
        execution_time=0.1, category=category,
    )
    return sandbox


def _make_extracted(content: str, path="/app/output.csv"):
    return ExtractedFile(
        path=path,
        content_bytes=content.encode("utf-8"),
        size=len(content.encode("utf-8")),
        content_text=content,
        encoding="utf-8",
    )


def _make_extracted_bytes(content_bytes: bytes, path="/app/model.pkl"):
    return ExtractedFile(
        path=path,
        content_bytes=content_bytes,
        size=len(content_bytes),
        content_text="",
        encoding="utf-8",
    )


# ===============================================================
# TestExpectStdoutValue
# ===============================================================

class TestExpectStdoutValueSuccess(unittest.TestCase):
    """Tests for successful value extraction and comparison."""

    def setUp(self):
        self.test = ExpectStdoutValueTest()

    def test_exact_match(self):
        """Extracted value exactly matches expected value."""
        sandbox = _make_sandbox(stdout="total_rows: 1500")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py stats",
            extraction_pattern=r"total_rows:\s*(?P<value>\d+)",
            expected_value=1500,
            tolerance=0,
        )
        self.assertEqual(result.score, 100.0)

    def test_match_with_tolerance(self):
        """Extracted value within tolerance of expected value."""
        sandbox = _make_sandbox(stdout="accuracy: 0.847")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            extraction_pattern=r"accuracy:\s*(?P<value>[\d.]+)",
            expected_value=0.85,
            tolerance=0.01,
        )
        self.assertEqual(result.score, 100.0)

    def test_match_outside_tolerance(self):
        """Extracted value outside tolerance of expected value."""
        sandbox = _make_sandbox(stdout="accuracy: 0.70")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            extraction_pattern=r"accuracy:\s*(?P<value>[\d.]+)",
            expected_value=0.85,
            tolerance=0.01,
        )
        self.assertEqual(result.score, 0.0)


class TestExpectStdoutValueErrors(unittest.TestCase):
    """Tests for error handling in ExpectStdoutValueTest."""

    def setUp(self):
        self.test = ExpectStdoutValueTest()

    def test_no_match_in_stdout(self):
        """Pattern doesn't match anything in stdout."""
        sandbox = _make_sandbox(stdout="no relevant output here")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            extraction_pattern=r"total_rows:\s*(?P<value>\d+)",
            expected_value=1500,
        )
        self.assertEqual(result.score, 0.0)
        self.assertIn("total_rows", result.report)

    def test_non_numeric_value(self):
        """Extracted value is not a valid number."""
        sandbox = _make_sandbox(stdout="total_rows: abc")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            extraction_pattern=r"total_rows:\s*(?P<value>\w+)",
            expected_value=1500,
        )
        self.assertEqual(result.score, 0.0)
        self.assertIn("abc", result.report)

    def test_timeout(self):
        """Program times out."""
        sandbox = _make_sandbox(
            stderr="Execution timed out",
            exit_code=124,
            category=ResponseCategory.TIMEOUT,
        )
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            extraction_pattern=r"total_rows:\s*(?P<value>\d+)",
            expected_value=1500,
        )
        self.assertEqual(result.score, 0.0)

    def test_runtime_error(self):
        """Program crashes with runtime error."""
        sandbox = _make_sandbox(
            stderr="ImportError: No module named 'pandas'",
            exit_code=1,
            category=ResponseCategory.RUNTIME_ERROR,
        )
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            extraction_pattern=r"total_rows:\s*(?P<value>\d+)",
            expected_value=1500,
        )
        self.assertEqual(result.score, 0.0)


# ===============================================================
# TestExpectMetric
# ===============================================================

class TestExpectMetricConditions(unittest.TestCase):
    """Tests for each comparison condition in ExpectMetricTest."""

    def setUp(self):
        self.test = ExpectMetricTest()

    def test_gte_pass(self):
        """Metric >= threshold."""
        sandbox = _make_sandbox(stdout="accuracy: 0.90")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"accuracy:\s*(?P<value>[\d.]+)",
            condition=">=",
            threshold=0.85,
        )
        self.assertEqual(result.score, 100.0)

    def test_gte_fail(self):
        """Metric < threshold."""
        sandbox = _make_sandbox(stdout="accuracy: 0.70")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"accuracy:\s*(?P<value>[\d.]+)",
            condition=">=",
            threshold=0.85,
        )
        self.assertEqual(result.score, 0.0)

    def test_lte_pass(self):
        """Metric <= threshold (e.g., RMSE)."""
        sandbox = _make_sandbox(stdout="rmse: 2.3")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"rmse:\s*(?P<value>[\d.]+)",
            condition="<=",
            threshold=3.0,
        )
        self.assertEqual(result.score, 100.0)

    def test_gt_pass(self):
        """Metric > threshold."""
        sandbox = _make_sandbox(stdout="f1: 0.91")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"f1:\s*(?P<value>[\d.]+)",
            condition=">",
            threshold=0.90,
        )
        self.assertEqual(result.score, 100.0)

    def test_lt_pass(self):
        """Metric < threshold."""
        sandbox = _make_sandbox(stdout="loss: 0.05")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"loss:\s*(?P<value>[\d.]+)",
            condition="<",
            threshold=0.1,
        )
        self.assertEqual(result.score, 100.0)

    def test_eq_pass(self):
        """Metric == threshold."""
        sandbox = _make_sandbox(stdout="epochs: 10")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"epochs:\s*(?P<value>[\d.]+)",
            condition="==",
            threshold=10.0,
        )
        self.assertEqual(result.score, 100.0)

    def test_eq_fail(self):
        """Metric != threshold."""
        sandbox = _make_sandbox(stdout="epochs: 5")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"epochs:\s*(?P<value>[\d.]+)",
            condition="==",
            threshold=10.0,
        )
        self.assertEqual(result.score, 0.0)


class TestExpectMetricErrors(unittest.TestCase):
    """Tests for error handling in ExpectMetricTest."""

    def setUp(self):
        self.test = ExpectMetricTest()

    def test_invalid_condition(self):
        """Invalid condition operator is rejected."""
        sandbox = _make_sandbox(stdout="accuracy: 0.90")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"accuracy:\s*(?P<value>[\d.]+)",
            condition="!=",
            threshold=0.85,
        )
        self.assertEqual(result.score, 0.0)
        self.assertIn("!=", result.report)

    def test_no_match_in_stdout(self):
        """Pattern doesn't match anything in stdout."""
        sandbox = _make_sandbox(stdout="no metrics here")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"accuracy:\s*(?P<value>[\d.]+)",
            condition=">=",
            threshold=0.85,
        )
        self.assertEqual(result.score, 0.0)

    def test_non_numeric_metric(self):
        """Extracted metric is not a valid number."""
        sandbox = _make_sandbox(stdout="accuracy: N/A")
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            metric_pattern=r"accuracy:\s*(?P<value>\S+)",
            condition=">=",
            threshold=0.85,
        )
        self.assertEqual(result.score, 0.0)


# ===============================================================
# TestExpectCsvOutput
# ===============================================================

class TestExpectCsvOutputColumns(unittest.TestCase):
    """Tests for column validation in ExpectCsvOutputTest."""

    def setUp(self):
        self.test = ExpectCsvOutputTest()

    def test_columns_match(self):
        """Columns match expected names and order."""
        csv_content = "name,cuisine,rating\nPizza Place,Italian,4.5\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py preprocess",
            artifact_path="output.csv",
            expected_columns=["name", "cuisine", "rating"],
        )
        self.assertEqual(result.score, 100.0)

    def test_columns_mismatch(self):
        """Columns don't match expected."""
        csv_content = "name,type,score\nPizza Place,Italian,4.5\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py preprocess",
            artifact_path="output.csv",
            expected_columns=["name", "cuisine", "rating"],
        )
        self.assertEqual(result.score, 0.0)


class TestExpectCsvOutputShape(unittest.TestCase):
    """Tests for shape validation in ExpectCsvOutputTest."""

    def setUp(self):
        self.test = ExpectCsvOutputTest()

    def test_shape_match(self):
        """Shape matches expected rows and columns."""
        csv_content = "a,b,c\n1,2,3\n4,5,6\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_shape=[2, 3],
        )
        self.assertEqual(result.score, 100.0)

    def test_shape_mismatch(self):
        """Shape doesn't match expected."""
        csv_content = "a,b\n1,2\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_shape=[3, 3],
        )
        self.assertEqual(result.score, 0.0)


class TestExpectCsvOutputValues(unittest.TestCase):
    """Tests for value validation with tolerance in ExpectCsvOutputTest."""

    def setUp(self):
        self.test = ExpectCsvOutputTest()

    def test_values_exact_match(self):
        """Values match exactly."""
        csv_content = "id,score\n1,95.0\n2,87.5\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_values=[["1", "95.0"], ["2", "87.5"]],
        )
        self.assertEqual(result.score, 100.0)

    def test_values_within_tolerance(self):
        """Numeric values within tolerance."""
        csv_content = "id,score\n1,95.3\n2,87.2\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_values=[["1", "95.0"], ["2", "87.5"]],
            tolerance=0.5,
        )
        self.assertEqual(result.score, 100.0)

    def test_proportional_scoring(self):
        """Partial match gives proportional score."""
        csv_content = "id,score\n1,95.0\n2,0.0\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_values=[["1", "95.0"], ["2", "87.5"]],
            tolerance=0,
        )
        # 3 out of 4 cells match (id=1, score=95.0, id=2 match; score=0.0 doesn't)
        self.assertGreater(result.score, 0.0)
        self.assertLess(result.score, 100.0)


class TestExpectCsvOutputErrors(unittest.TestCase):
    """Tests for error handling in ExpectCsvOutputTest."""

    def setUp(self):
        self.test = ExpectCsvOutputTest()

    def test_file_not_found(self):
        """CSV artifact not found in sandbox."""
        sandbox = _make_sandbox()
        sandbox.extract_file.side_effect = FileNotFoundError("File not found")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_columns=["a", "b"],
        )
        self.assertEqual(result.score, 0.0)
        self.assertIn("output.csv", result.report)

    def test_invalid_path(self):
        """Absolute path is rejected."""
        sandbox = _make_sandbox()
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="/etc/passwd",
            expected_columns=["a"],
        )
        self.assertEqual(result.score, 0.0)

    def test_empty_artifact_path(self):
        """Empty artifact path is rejected."""
        sandbox = _make_sandbox()
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="",
        )
        self.assertEqual(result.score, 0.0)

    def test_no_checks_specified(self):
        """File exists with no specific checks = pass."""
        csv_content = "a,b\n1,2\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
        )
        self.assertEqual(result.score, 100.0)

    def test_combined_checks_proportional(self):
        """Multiple checks contribute proportionally to score."""
        csv_content = "name,score\nAlice,95\nBob,80\n"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(csv_content)

        # Columns match, shape doesn't
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 analysis.py",
            artifact_path="output.csv",
            expected_columns=["name", "score"],
            expected_shape=[5, 2],  # Wrong rows
        )
        self.assertEqual(result.score, 50.0)


# ===============================================================
# TestExpectJsonOutput
# ===============================================================

class TestExpectJsonOutputKeys(unittest.TestCase):
    """Tests for key validation in ExpectJsonOutputTest."""

    def setUp(self):
        self.test = ExpectJsonOutputTest()

    def test_required_keys_found(self):
        """All required keys found."""
        data = {"accuracy": 0.9, "loss": 0.1, "epochs": 10}
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(json.dumps(data), path="/app/metrics.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            required_keys=["accuracy", "loss", "epochs"],
        )
        self.assertEqual(result.score, 100.0)

    def test_required_key_missing(self):
        """One required key missing."""
        data = {"accuracy": 0.9, "loss": 0.1}
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(json.dumps(data), path="/app/metrics.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            required_keys=["accuracy", "loss", "epochs"],
        )
        self.assertGreater(result.score, 0.0)
        self.assertLess(result.score, 100.0)

    def test_nested_key_found(self):
        """Nested key access via dot notation."""
        data = {"metrics": {"accuracy": 0.9}}
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(json.dumps(data), path="/app/results.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="results.json",
            required_keys=["metrics.accuracy"],
        )
        self.assertEqual(result.score, 100.0)


class TestExpectJsonOutputValues(unittest.TestCase):
    """Tests for value validation in ExpectJsonOutputTest."""

    def setUp(self):
        self.test = ExpectJsonOutputTest()

    def test_value_match(self):
        """Expected value matches actual value."""
        data = {"accuracy": 0.9, "model": "rf"}
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(json.dumps(data), path="/app/metrics.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            expected_values={"model": "rf"},
        )
        self.assertEqual(result.score, 100.0)

    def test_numeric_value_with_tolerance(self):
        """Numeric value within tolerance."""
        data = {"accuracy": 0.847}
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(json.dumps(data), path="/app/metrics.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            expected_values={"accuracy": 0.85},
            tolerance=0.01,
        )
        self.assertEqual(result.score, 100.0)

    def test_value_mismatch(self):
        """Expected value doesn't match actual value."""
        data = {"accuracy": 0.5}
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted(json.dumps(data), path="/app/metrics.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            expected_values={"accuracy": 0.9},
            tolerance=0.01,
        )
        self.assertEqual(result.score, 0.0)


class TestExpectJsonOutputErrors(unittest.TestCase):
    """Tests for error handling in ExpectJsonOutputTest."""

    def setUp(self):
        self.test = ExpectJsonOutputTest()

    def test_file_not_found(self):
        """JSON file not found."""
        sandbox = _make_sandbox()
        sandbox.extract_file.side_effect = FileNotFoundError("File not found")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            required_keys=["accuracy"],
        )
        self.assertEqual(result.score, 0.0)

    def test_invalid_json(self):
        """File content is not valid JSON."""
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted("not json {{{", path="/app/metrics.json")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="metrics.json",
            required_keys=["accuracy"],
        )
        self.assertEqual(result.score, 0.0)

    def test_invalid_path(self):
        """Absolute path is rejected."""
        sandbox = _make_sandbox()
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="/etc/passwd",
        )
        self.assertEqual(result.score, 0.0)


# ===============================================================
# TestExpectModelArtifact
# ===============================================================

class TestExpectModelArtifactSuccess(unittest.TestCase):
    """Tests for successful model artifact validation."""

    def setUp(self):
        self.test = ExpectModelArtifactTest()

    def test_model_exists_sufficient_size(self):
        """Model file exists and meets minimum size."""
        content = b"\x80\x04" + b"\x00" * 4096  # Simulate a pickle file
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted_bytes(content, path="/app/model.pkl")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="model.pkl",
            min_size_bytes=2048,
        )
        self.assertEqual(result.score, 100.0)

    def test_model_exists_no_min_size(self):
        """Model file exists with no min_size requirement."""
        content = b"\x80\x04\x95"
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted_bytes(content, path="/app/model.pkl")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="model.pkl",
        )
        self.assertEqual(result.score, 100.0)


class TestExpectModelArtifactErrors(unittest.TestCase):
    """Tests for error handling in ExpectModelArtifactTest."""

    def setUp(self):
        self.test = ExpectModelArtifactTest()

    def test_model_too_small(self):
        """Model file exists but is too small."""
        content = b"\x80"  # 1 byte
        sandbox = _make_sandbox()
        sandbox.extract_file.return_value = _make_extracted_bytes(content, path="/app/model.pkl")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="model.pkl",
            min_size_bytes=2048,
        )
        self.assertEqual(result.score, 0.0)
        self.assertIn("too small", result.report.lower())

    def test_model_not_found(self):
        """Model file not found."""
        sandbox = _make_sandbox()
        sandbox.extract_file.side_effect = FileNotFoundError("File not found")

        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="model.pkl",
            min_size_bytes=2048,
        )
        self.assertEqual(result.score, 0.0)
        self.assertIn("model.pkl", result.report)

    def test_invalid_path(self):
        """Absolute path is rejected."""
        sandbox = _make_sandbox()
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="/tmp/model.pkl",
            min_size_bytes=2048,
        )
        self.assertEqual(result.score, 0.0)

    def test_traversal_path_rejected(self):
        """Path traversal is rejected."""
        sandbox = _make_sandbox()
        result = self.test.execute(
            files=None, sandbox=sandbox,
            program_command="python3 train.py",
            artifact_path="../model.pkl",
            min_size_bytes=2048,
        )
        self.assertEqual(result.score, 0.0)


# ===============================================================
# TestDataScienceTemplate
# ===============================================================

class TestDataScienceTemplate(unittest.TestCase):
    """Tests for the DataScienceTemplate class."""

    def setUp(self):
        self.template = DataScienceTemplate()

    def test_contract_validation(self):
        """Template passes contract validation."""
        self.template.validate_contract()
        self.assertIsInstance(self.template.get_tests(), dict)

    def test_requires_sandbox(self):
        """Template requires sandbox."""
        self.assertTrue(self.template.requires_sandbox)

    def test_template_name_not_empty(self):
        """Template name is not empty."""
        self.assertTrue(len(self.template.template_name) > 0)

    def test_template_description_not_empty(self):
        """Template description is not empty."""
        self.assertTrue(len(self.template.template_description) > 0)

    def test_get_test_expect_stdout_value(self):
        """Can retrieve expect_stdout_value test."""
        test = self.template.get_test("expect_stdout_value")
        self.assertIsInstance(test, ExpectStdoutValueTest)

    def test_get_test_expect_metric(self):
        """Can retrieve expect_metric test."""
        test = self.template.get_test("expect_metric")
        self.assertIsInstance(test, ExpectMetricTest)

    def test_get_test_expect_csv_output(self):
        """Can retrieve expect_csv_output test."""
        test = self.template.get_test("expect_csv_output")
        self.assertIsInstance(test, ExpectCsvOutputTest)

    def test_get_test_expect_json_output(self):
        """Can retrieve expect_json_output test."""
        test = self.template.get_test("expect_json_output")
        self.assertIsInstance(test, ExpectJsonOutputTest)

    def test_get_test_expect_model_artifact(self):
        """Can retrieve expect_model_artifact test."""
        test = self.template.get_test("expect_model_artifact")
        self.assertIsInstance(test, ExpectModelArtifactTest)

    def test_get_nonexistent_test_raises(self):
        """Getting a non-existent test raises AttributeError."""
        with self.assertRaises(AttributeError):
            self.template.get_test("nonexistent_test")

    def test_all_tests_registered(self):
        """All 5 test functions are registered."""
        tests = self.template.get_tests()
        expected_names = {
            "expect_stdout_value",
            "expect_metric",
            "expect_csv_output",
            "expect_json_output",
            "expect_model_artifact",
        }
        self.assertEqual(set(tests.keys()), expected_names)


# ===============================================================
# TestExpectStdoutValueMetadata
# ===============================================================

class TestExpectStdoutValueMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectStdoutValueTest."""

    def test_name(self):
        """Test the template name."""
        self.assertEqual(ExpectStdoutValueTest().name, "expect_stdout_value")

    def test_description_not_empty(self):
        """Test the description is not empty."""
        self.assertTrue(len(ExpectStdoutValueTest().description) > 0)

    def test_parameter_descriptions(self):
        """Test parameter descriptions exist."""
        params = ExpectStdoutValueTest().parameter_description
        names = [p.name for p in params]
        self.assertIn("program_command", names)
        self.assertIn("extraction_pattern", names)
        self.assertIn("expected_value", names)
        self.assertIn("tolerance", names)


class TestExpectMetricMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectMetricTest."""

    def test_name(self):
        """Test the template name."""
        self.assertEqual(ExpectMetricTest().name, "expect_metric")

    def test_description_not_empty(self):
        """Test the description is not empty."""
        self.assertTrue(len(ExpectMetricTest().description) > 0)

    def test_parameter_descriptions(self):
        """Test parameter descriptions exist."""
        params = ExpectMetricTest().parameter_description
        names = [p.name for p in params]
        self.assertIn("program_command", names)
        self.assertIn("metric_pattern", names)
        self.assertIn("condition", names)
        self.assertIn("threshold", names)


class TestExpectCsvOutputMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectCsvOutputTest."""

    def test_name(self):
        """Test the template name."""
        self.assertEqual(ExpectCsvOutputTest().name, "expect_csv_output")

    def test_description_not_empty(self):
        """Test the description is not empty."""
        self.assertTrue(len(ExpectCsvOutputTest().description) > 0)


class TestExpectJsonOutputMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectJsonOutputTest."""

    def test_name(self):
        """Test the template name."""
        self.assertEqual(ExpectJsonOutputTest().name, "expect_json_output")

    def test_description_not_empty(self):
        """Test the description is not empty."""
        self.assertTrue(len(ExpectJsonOutputTest().description) > 0)


class TestExpectModelArtifactMetadata(unittest.TestCase):
    """Tests for metadata properties of ExpectModelArtifactTest."""

    def test_name(self):
        """Test the template name."""
        self.assertEqual(ExpectModelArtifactTest().name, "expect_model_artifact")

    def test_description_not_empty(self):
        """Test the description is not empty."""
        self.assertTrue(len(ExpectModelArtifactTest().description) > 0)


if __name__ == "__main__":
    unittest.main()
