"""Tests for ComplexityTest, ComplexityClassifier, and InputGenerator."""

import math
from unittest.mock import MagicMock, patch

import pytest

from autograder.template_library.complexity.classifier import ComplexityClassifier
from autograder.template_library.complexity.test_function import ComplexityTest
from autograder.template_library.complexity.generators import InputGenerator
from autograder.template_library.complexity.scoring import ComplexityScorer
from autograder.template_library.input_output import InputOutputTemplate
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import ResponseCategory


# ===============================================================
# ComplexityClassifier Tests
# ===============================================================


class TestComplexityClassifierDetection:
    """Test that the classifier correctly identifies common complexity classes."""

    def test_detects_constant(self):
        # O(1): time does not grow with size
        data = [(500, 100), (2500, 102), (12500, 98), (62500, 101)]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(1)"

    def test_detects_linear(self):
        # O(n): time grows proportionally to n
        data = [(500, 500), (2500, 2500), (12500, 12500), (62500, 62500)]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(n)"
        assert r2 > 0.95

    def test_detects_quadratic(self):
        # O(n^2): time grows as n^2
        data = [(100, 10), (200, 40), (400, 160), (800, 640)]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(n^2)"
        assert r2 > 0.95

    def test_detects_cubic(self):
        # O(n^3): time grows as n^3
        data = [(50, 125000), (100, 1000000), (200, 8000000), (400, 64000000)]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(n^3)"
        assert r2 > 0.95

    def test_detects_nlogn(self):
        # O(n log n): use wider size range for better log factor discrimination
        sizes = [100, 1000, 10000, 100000]
        data = [(s, s * math.log2(s)) for s in sizes]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(n log n)"
        assert r2 > 0.95

    def test_detects_sqrt(self):
        # O(sqrt(n)): alpha ~ 0.5
        data = [
            (100, math.sqrt(100)),
            (400, math.sqrt(400)),
            (1600, math.sqrt(1600)),
            (6400, math.sqrt(6400)),
        ]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(sqrt(n))"

    def test_all_zero_times_returns_constant(self):
        data = [(500, 0), (2500, 0), (12500, 0), (62500, 0)]
        result, r2 = ComplexityClassifier.classify(data)
        assert result == "O(1)"

    def test_too_few_valid_measurements(self):
        data = [(500, 0), (2500, 0), (12500, 5)]
        result, _ = ComplexityClassifier.classify(data)
        assert result == "O(1)"


class TestComplexityClassifierMath:
    """Test internal math helpers."""

    def test_fit_power_law_perfect_linear(self):
        sizes = [100, 200, 400, 800]
        times = [100.0, 200.0, 400.0, 800.0]
        alpha, r2 = ComplexityClassifier._fit_power_law(sizes, times)
        assert abs(alpha - 1.0) < 0.1
        assert r2 > 0.99

    def test_fit_power_law_perfect_quadratic(self):
        sizes = [100, 200, 400, 800]
        times = [10000.0, 40000.0, 160000.0, 640000.0]
        alpha, r2 = ComplexityClassifier._fit_power_law(sizes, times)
        assert abs(alpha - 2.0) < 0.1
        assert r2 > 0.99

    def test_fit_model_linear(self):
        sizes = [100, 200, 400, 800]
        times = [100.0, 200.0, 400.0, 800.0]
        r2 = ComplexityClassifier._fit_model(sizes, times, lambda n: n)
        assert r2 > 0.99

    def test_fit_model_nlogn(self):
        sizes = [500, 2500, 12500, 62500]
        times = [s * math.log2(s) for s in sizes]
        r2 = ComplexityClassifier._fit_model(sizes, times, lambda n: n * math.log2(n))
        assert r2 > 0.99


# ===============================================================
# InputGenerator Tests
# ===============================================================


class TestInputGenerator:
    """Test input generators."""

    def test_random_array_format(self):
        result = InputGenerator.generate("random_array", 5)
        lines = result.strip().split("\n")
        assert lines[0] == "5"
        values = lines[1].split()
        assert len(values) == 5

    def test_sorted_array_is_sorted(self):
        result = InputGenerator.generate("sorted_array", 10)
        lines = result.strip().split("\n")
        values = list(map(int, lines[1].split()))
        assert values == sorted(values)

    def test_reverse_sorted_array(self):
        result = InputGenerator.generate("reverse_sorted_array", 10)
        lines = result.strip().split("\n")
        values = list(map(int, lines[1].split()))
        assert values == sorted(values, reverse=True)

    def test_random_string_length(self):
        result = InputGenerator.generate("random_string", 100)
        assert len(result) == 100
        assert result.isalpha()

    def test_random_pairs_format(self):
        result = InputGenerator.generate("random_pairs", 5)
        lines = result.strip().split("\n")
        assert lines[0] == "5"
        assert len(lines) == 6  # header + 5 pairs
        for line in lines[1:]:
            parts = line.split()
            assert len(parts) == 2

    def test_single_number(self):
        result = InputGenerator.generate("single_number", 42)
        assert result == "42"

    def test_random_matrix_format(self):
        result = InputGenerator.generate("random_matrix", 3)
        lines = result.strip().split("\n")
        assert lines[0] == "3"
        assert len(lines) == 4  # header + 3 rows
        for line in lines[1:]:
            assert len(line.split()) == 3

    def test_custom_min_max_values(self):
        result = InputGenerator.generate(
            "random_array", 100, input_args={"min_value": 1, "max_value": 10}
        )
        lines = result.strip().split("\n")
        values = list(map(int, lines[1].split()))
        assert all(1 <= v <= 10 for v in values)

    def test_unknown_generator_raises(self):
        with pytest.raises(ValueError, match="Unknown input generator"):
            InputGenerator.generate("nonexistent", 10)


# ===============================================================
# Scoring Tests
# ===============================================================


class TestComplexityScorer:
    """Test scoring logic."""

    def test_strict_exact_match(self):
        assert ComplexityScorer.score("O(n)", "O(n)", "strict") == 100.0

    def test_strict_better_than_expected(self):
        assert ComplexityScorer.score("O(1)", "O(n)", "strict") == 100.0

    def test_strict_worse_than_expected(self):
        assert ComplexityScorer.score("O(n^2)", "O(n)", "strict") == 0.0

    def test_graduated_exact_match(self):
        assert ComplexityScorer.score("O(n log n)", "O(n log n)", "graduated") == 100.0

    def test_graduated_better_than_expected(self):
        assert ComplexityScorer.score("O(n)", "O(n log n)", "graduated") == 100.0

    def test_graduated_one_class_above(self):
        assert ComplexityScorer.score("O(n^2)", "O(n log n)", "graduated") == 80.0

    def test_graduated_two_classes_above(self):
        assert ComplexityScorer.score("O(n^3)", "O(n log n)", "graduated") == 60.0

    def test_graduated_three_classes_above(self):
        assert ComplexityScorer.score("O(exponential)", "O(n log n)", "graduated") == 30.0

    def test_graduated_four_or_more_classes_above(self):
        assert ComplexityScorer.score("O(exponential)", "O(n)", "graduated") == 0.0

    def test_custom_score_table(self):
        table = {"O(n)": 100, "O(n log n)": 100, "O(n^2)": 70, "O(n^3)": 30}
        assert ComplexityScorer.score("O(n^2)", "O(n log n)", "custom", table) == 70.0
        assert ComplexityScorer.score("O(n^3)", "O(n log n)", "custom", table) == 30.0

    def test_custom_not_in_table_better(self):
        table = {"O(n^2)": 50}
        assert ComplexityScorer.score("O(1)", "O(n)", "custom", table) == 100.0

    def test_custom_not_in_table_worse(self):
        table = {"O(n)": 100}
        assert ComplexityScorer.score("O(n^2)", "O(n)", "custom", table) == 0.0

    def test_unknown_scoring_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown scoring mode"):
            ComplexityScorer.score("O(n)", "O(n)", "invalid")


# ===============================================================
# ComplexityTest Registration & Metadata Tests
# ===============================================================


class TestComplexityTestRegistration:
    """Test that ComplexityTest is properly registered in the template."""

    def test_complexity_registered_in_template(self):
        template = InputOutputTemplate()
        test = template.get_test("complexity")
        assert test is not None
        assert test.name == "complexity"

    def test_all_original_tests_still_registered(self):
        template = InputOutputTemplate()
        assert template.get_test("expect_output") is not None
        assert template.get_test("dont_fail") is not None
        assert template.get_test("forbidden_import") is not None


class TestComplexityTestMetadata:
    """Test ComplexityTest metadata and properties."""

    def setup_method(self):
        self.test_fn = ComplexityTest()

    def test_name(self):
        assert self.test_fn.name == "complexity"

    def test_description_not_empty(self):
        assert len(self.test_fn.description) > 0

    def test_parameter_descriptions(self):
        params = self.test_fn.parameter_description
        param_names = [p.name for p in params]
        assert "program_command" in param_names
        assert "expected_complexity" in param_names
        assert "input_generator" in param_names
        assert "scoring" in param_names


class TestComplexityTestExecution:
    """Test ComplexityTest execute method edge cases (without real sandbox)."""

    def setup_method(self):
        self.test_fn = ComplexityTest()

    def test_no_sandbox_returns_zero(self):
        result = self.test_fn.execute(
            files=[], sandbox=None, program_command="python3 main.py"
        )
        assert result.score == 0.0
        assert result.test_name == "complexity"

    def test_no_command_returns_zero(self):
        sandbox = MagicMock(spec=SandboxContainer)
        result = self.test_fn.execute(files=[], sandbox=sandbox, program_command=None)
        assert result.score == 0.0

    def test_invalid_generator_returns_zero(self):
        sandbox = MagicMock(spec=SandboxContainer)
        result = self.test_fn.execute(
            files=[],
            sandbox=sandbox,
            program_command="python3 main.py",
            input_generator="nonexistent_generator",
        )
        assert result.score == 0.0

    def test_benchmark_timeout_returns_zero(self):
        sandbox = MagicMock(spec=SandboxContainer)
        sandbox.container_ref = MagicMock()
        sandbox.container_ref.exec_run.return_value = MagicMock(exit_code=0)
        sandbox.run_command.return_value = MagicMock(
            category=ResponseCategory.TIMEOUT,
            stdout="",
        )
        result = self.test_fn.execute(
            files=[],
            sandbox=sandbox,
            program_command="python3 main.py",
            test_sizes=[10, 50, 250, 1250],
        )
        assert result.score == 0.0

    def test_successful_classification(self):
        """Test full flow with mocked sandbox returning O(n^2) data."""
        sandbox = MagicMock(spec=SandboxContainer)
        sandbox.container_ref = MagicMock()
        sandbox.container_ref.exec_run.return_value = MagicMock(exit_code=0)

        import json
        results = [
            {"size": 100, "time_us": 10},
            {"size": 200, "time_us": 40},
            {"size": 400, "time_us": 160},
            {"size": 800, "time_us": 640},
        ]
        sandbox.run_command.return_value = MagicMock(
            category=ResponseCategory.SUCCESS,
            stdout=f"COMPLEXITY_RESULTS:{json.dumps(results)}\n",
        )

        result = self.test_fn.execute(
            files=[],
            sandbox=sandbox,
            program_command="python3 main.py",
            expected_complexity="O(n^2)",
            scoring="strict",
            test_sizes=[100, 200, 400, 800],
        )
        assert result.score == 100.0

    def test_graduated_scoring_with_worse_complexity(self):
        """Test graduated scoring when detected is worse than expected."""
        sandbox = MagicMock(spec=SandboxContainer)
        sandbox.container_ref = MagicMock()
        sandbox.container_ref.exec_run.return_value = MagicMock(exit_code=0)

        import json
        # O(n^2) data
        results = [
            {"size": 100, "time_us": 10000},
            {"size": 200, "time_us": 40000},
            {"size": 400, "time_us": 160000},
            {"size": 800, "time_us": 640000},
        ]
        sandbox.run_command.return_value = MagicMock(
            category=ResponseCategory.SUCCESS,
            stdout=f"COMPLEXITY_RESULTS:{json.dumps(results)}\n",
        )

        result = self.test_fn.execute(
            files=[],
            sandbox=sandbox,
            program_command="python3 main.py",
            expected_complexity="O(n log n)",
            scoring="graduated",
            test_sizes=[100, 200, 400, 800],
        )
        # O(n^2) is 1 class above O(n log n) → 80
        assert result.score == 80.0

    def test_inconclusive_partial_policy(self):
        """Test inconclusive measurement with partial policy gives 50."""
        sandbox = MagicMock(spec=SandboxContainer)
        sandbox.container_ref = MagicMock()
        sandbox.container_ref.exec_run.return_value = MagicMock(exit_code=0)

        import json
        # Highly erratic data that won't fit any model well (R² < 0.85)
        results = [
            {"size": 500, "time_us": 50000},
            {"size": 2500, "time_us": 3000},
            {"size": 12500, "time_us": 800000},
            {"size": 62500, "time_us": 10000},
        ]
        sandbox.run_command.return_value = MagicMock(
            category=ResponseCategory.SUCCESS,
            stdout=f"COMPLEXITY_RESULTS:{json.dumps(results)}\n",
        )

        result = self.test_fn.execute(
            files=[],
            sandbox=sandbox,
            program_command="python3 main.py",
            expected_complexity="O(n)",
            scoring="graduated",
            inconclusive_policy="partial",
        )
        assert result.score == 50.0

    def test_runtime_error_from_benchmark(self):
        """Test handling of runtime errors reported by the benchmark wrapper."""
        sandbox = MagicMock(spec=SandboxContainer)
        sandbox.container_ref = MagicMock()
        sandbox.container_ref.exec_run.return_value = MagicMock(exit_code=0)
        sandbox.run_command.return_value = MagicMock(
            category=ResponseCategory.SUCCESS,
            stdout="COMPLEXITY_ERROR:runtime_error|500|IndexError: list index out of range\n",
        )

        result = self.test_fn.execute(
            files=[],
            sandbox=sandbox,
            program_command="python3 main.py",
            test_sizes=[10, 50, 250, 1250],
        )
        assert result.score == 0.0


class TestComplexityTestParseOutput:
    """Test output parsing logic."""

    def setup_method(self):
        self.test_fn = ComplexityTest()

    def test_parse_valid_results(self):
        stdout = 'COMPLEXITY_RESULTS:[{"size":500,"time_us":1234},{"size":2500,"time_us":7891}]\n'
        measurements, error = self.test_fn._parse_output(stdout)
        assert error is None
        assert len(measurements) == 2
        assert measurements[0] == (500, 1234)
        assert measurements[1] == (2500, 7891)

    def test_parse_error_output(self):
        stdout = "COMPLEXITY_ERROR:timeout|12500\n"
        measurements, error = self.test_fn._parse_output(stdout)
        assert measurements == []
        assert error == "timeout|12500"

    def test_parse_no_markers(self):
        stdout = "Some random output\nfrom the program\n"
        measurements, error = self.test_fn._parse_output(stdout)
        assert measurements == []
        assert error is None

    def test_parse_with_extra_lines(self):
        stdout = "Loading...\nCOMPLEXITY_RESULTS:[{\"size\":100,\"time_us\":50}]\nDone.\n"
        measurements, error = self.test_fn._parse_output(stdout)
        assert len(measurements) == 1
        assert measurements[0] == (100, 50)
