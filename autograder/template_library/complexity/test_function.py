import json
import logging
from typing import Dict, List, Optional, Tuple

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import ResponseCategory

from autograder.template_library.complexity.classifier import ComplexityClassifier
from autograder.template_library.complexity.generators import InputGenerator
from autograder.template_library.complexity.scoring import ComplexityScorer

logger = logging.getLogger(__name__)


# ===============================================================
# Benchmark Wrapper Script
# ===============================================================

_BENCHMARK_SCRIPT = r'''#!/usr/bin/env python3
"""Auto-generated benchmark wrapper — Autograder ComplexityTest."""

import subprocess
import time
import sys
import json

PROGRAM_CMD = sys.argv[1]
INPUTS_FILE = "/app/_inputs.json"
REPEATS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
TIMEOUT = int(sys.argv[3]) if len(sys.argv) > 3 else 30

def run_once(cmd, input_data, timeout_s):
    start = time.perf_counter()
    proc = subprocess.run(
        cmd, shell=True, input=input_data,
        capture_output=True, text=True, timeout=timeout_s
    )
    elapsed_us = (time.perf_counter() - start) * 1_000_000
    return elapsed_us, proc.returncode, proc.stderr

def main():
    with open(INPUTS_FILE, "r") as f:
        entries = json.load(f)

    results = []

    # Warmup run
    try:
        run_once(PROGRAM_CMD, entries[0]["input"], TIMEOUT)
    except subprocess.TimeoutExpired:
        print("COMPLEXITY_ERROR:warmup_timeout")
        sys.exit(1)

    # Measurement runs
    for entry in entries:
        size = entry["size"]
        input_data = entry["input"]

        times = []
        for _ in range(REPEATS):
            try:
                elapsed_us, returncode, stderr = run_once(PROGRAM_CMD, input_data, TIMEOUT)

                if returncode != 0:
                    print(f"COMPLEXITY_ERROR:runtime_error|{size}|{stderr[:200]}")
                    sys.exit(1)

                times.append(elapsed_us)

            except subprocess.TimeoutExpired:
                print(f"COMPLEXITY_ERROR:timeout|{size}")
                sys.exit(1)

        min_time = min(times)
        results.append({"size": size, "time_us": min_time})

    print("COMPLEXITY_RESULTS:" + json.dumps(results))

if __name__ == "__main__":
    main()
'''


# ===============================================================
# ComplexityTest — TestFunction Implementation
# ===============================================================

class ComplexityTest(TestFunction):
    """
    Tests algorithmic complexity by running the student's program with
    multiple input sizes, measuring execution time inside the sandbox,
    and classifying the growth rate via log-log regression.
    """

    @property
    def name(self) -> str:
        return "complexity"

    @property
    def description(self) -> str:
        return t("io.complexity.description")

    @property
    def parameter_description(self) -> List[ParamDescription]:
        return [
            ParamDescription("program_command", t("io.complexity.params.program_command"), "string or dict"),
            ParamDescription("expected_complexity", t("io.complexity.params.expected_complexity"), "string"),
            ParamDescription("input_generator", t("io.complexity.params.input_generator"), "string"),
            ParamDescription("scoring", t("io.complexity.params.scoring"), "string"),
            ParamDescription("test_sizes", t("io.complexity.params.test_sizes"), "list of int"),
            ParamDescription("inconclusive_policy", t("io.complexity.params.inconclusive_policy"), "string"),
        ]

    def execute(
        self,
        files: Optional[List[SubmissionFile]],
        sandbox: Optional[SandboxContainer],
        *args,
        program_command: Optional[str] = None,
        expected_complexity: str = "O(n)",
        input_generator: str = "random_array",
        scoring: str = "graduated",
        score_table: Optional[Dict[str, int]] = None,
        inconclusive_policy: str = "partial",
        test_sizes: Optional[List[int]] = None,
        warmup: bool = True,
        repeats: int = 3,
        timeout: int = 30,
        input_args: Optional[Dict] = None,
        **kwargs,
    ) -> TestResult:
        locale = kwargs.get("locale")

        if sandbox is None:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.complexity.report.no_sandbox", locale=locale),
            )

        if program_command is None:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.complexity.report.no_command", locale=locale),
            )

        sizes = test_sizes or [500, 2500, 12500, 62500]

        # Validate input generator
        if input_generator not in InputGenerator.GENERATORS and input_generator != "custom":
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t(
                    "io.complexity.report.invalid_generator",
                    locale=locale,
                    generator=input_generator,
                ),
            )

        try:
            # Step 1: Generate inputs for all sizes
            inputs_data = []
            for size in sizes:
                input_str = InputGenerator.generate(input_generator, size, input_args)
                inputs_data.append({"size": size, "input": input_str})

            # Step 2: Inject benchmark wrapper + inputs into sandbox
            self._inject_benchmark_files(sandbox, inputs_data)

            # Step 3: Run the benchmark inside the sandbox
            bench_cmd = f"python3 /app/_benchmark.py '{program_command}' {repeats} {timeout}"
            output = sandbox.run_command(bench_cmd, timeout=timeout + 30)

            # Step 4: Parse results
            if output.category == ResponseCategory.TIMEOUT:
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=t("io.complexity.report.benchmark_timeout", locale=locale),
                )

            measurements, error = self._parse_output(output.stdout)

            if error:
                return self._handle_benchmark_error(error, locale)

            if not measurements:
                debug_info = f" \n--- DEBUG ---\nSTDOUT:\n{output.stdout}\nSTDERR:\n{output.stderr}\n"
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=t("io.complexity.report.no_results", locale=locale) + debug_info,
                )

            # Step 5: Classify complexity
            detected, r2 = ComplexityClassifier.classify(measurements)

            # Step 6: Check confidence
            if r2 < ComplexityClassifier.CONFIDENCE_THRESHOLD:
                return self._handle_inconclusive(
                    detected, r2, inconclusive_policy, expected_complexity,
                    scoring, score_table, measurements, sizes, locale,
                )

            # Step 7: Score
            grade = ComplexityScorer.score(detected, expected_complexity, scoring, score_table)

            return TestResult(
                test_name=self.name,
                score=grade,
                report=t(
                    "io.complexity.report.success",
                    locale=locale,
                    detected=detected,
                    expected=expected_complexity,
                    r2=f"{r2:.3f}",
                    grade=f"{grade:.0f}",
                ),
            )

        except Exception as e:
            logger.exception("Complexity test failed unexpectedly")
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.complexity.report.internal_error", locale=locale, error=str(e)),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _inject_benchmark_files(
        self, sandbox: SandboxContainer, inputs_data: List[Dict]
    ) -> None:
        """Inject _benchmark.py and _inputs.json into the sandbox."""
        import base64

        # Inject _benchmark.py
        script_b64 = base64.b64encode(_BENCHMARK_SCRIPT.encode("utf-8")).decode("ascii")
        sandbox.container_ref.exec_run(
            cmd=["/bin/sh", "-c", f"echo '{script_b64}' | base64 -d > /app/_benchmark.py"],
            user="sandbox",
        )

        # Inject _inputs.json in chunks (to bypass ARG_MAX shell limits)
        inputs_json = json.dumps(inputs_data)
        inputs_b64 = base64.b64encode(inputs_json.encode("utf-8")).decode("ascii")

        sandbox.container_ref.exec_run(
            cmd=["/bin/sh", "-c", "> /app/_inputs.b64"],
            user="sandbox"
        )

        chunk_size = 65000  # Safe size below typical 128KB ARG_MAX
        for i in range(0, len(inputs_b64), chunk_size):
            chunk = inputs_b64[i:i+chunk_size]
            sandbox.container_ref.exec_run(
                cmd=["/bin/sh", "-c", f"printf '%s' '{chunk}' >> /app/_inputs.b64"],
                user="sandbox"
            )

        sandbox.container_ref.exec_run(
            cmd=["/bin/sh", "-c", "base64 -d < /app/_inputs.b64 > /app/_inputs.json"],
            user="sandbox"
        )

    def _parse_output(self, stdout: str) -> Tuple[List[Tuple[int, float]], Optional[str]]:
        """
        Parse benchmark wrapper output.
        Returns (measurements, error_string).
        """
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("COMPLEXITY_RESULTS:"):
                json_str = line[len("COMPLEXITY_RESULTS:"):]
                data = json.loads(json_str)
                measurements = [(entry["size"], entry["time_us"]) for entry in data]
                return measurements, None
            if line.startswith("COMPLEXITY_ERROR:"):
                return [], line[len("COMPLEXITY_ERROR:"):]
        return [], None

    def _handle_benchmark_error(self, error: str, locale: Optional[str]) -> TestResult:
        """Convert a benchmark error string into a TestResult."""
        parts = error.split("|")
        error_type = parts[0]

        if error_type == "warmup_timeout":
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.complexity.report.warmup_timeout", locale=locale),
            )
        elif error_type == "timeout":
            size = parts[1] if len(parts) > 1 else "?"
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.complexity.report.size_timeout", locale=locale, size=size),
            )
        elif error_type == "runtime_error":
            size = parts[1] if len(parts) > 1 else "?"
            stderr = parts[2] if len(parts) > 2 else ""
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t(
                    "io.complexity.report.runtime_error",
                    locale=locale,
                    size=size,
                    error=stderr,
                ),
            )
        else:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.complexity.report.unknown_error", locale=locale, error=error),
            )

    def _handle_inconclusive(
        self,
        detected: str,
        r2: float,
        policy: str,
        expected_complexity: str,
        scoring: str,
        score_table: Optional[Dict[str, int]],
        measurements: List[Tuple[int, float]],
        sizes: List[int],
        locale: Optional[str],
    ) -> TestResult:
        """Handle inconclusive measurement (low R²)."""
        report = t(
            "io.complexity.report.inconclusive",
            locale=locale,
            r2=f"{r2:.3f}",
            detected=detected,
        )

        if policy == "pass":
            return TestResult(test_name=self.name, score=100.0, report=report)
        elif policy == "fail":
            return TestResult(test_name=self.name, score=0.0, report=report)
        elif policy == "retry":
            # Re-classify with same data (in practice the test would be re-run,
            # but the wrapper already took min-of-N so we treat this as final)
            grade = ComplexityScorer.score(detected, expected_complexity, scoring, score_table)
            return TestResult(test_name=self.name, score=grade, report=report)
        else:  # "partial" (default)
            return TestResult(test_name=self.name, score=50.0, report=report)
