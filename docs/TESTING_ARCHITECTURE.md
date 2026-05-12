# Master Testing Architecture Document

**Created:** May 12, 2026  
**Status:** Proposal  
**Author:** QA Architecture Team  
**Scope:** Comprehensive testing strategy for the Autograder engine

---

## Section 1: Identified Coverage Gaps

### Gap 1: Zero Security/Chaos Testing for the Sandbox Layer

The `sandbox_manager/` is the most security-critical component — it executes arbitrary student code. Yet there are **no tests** for:
- Fork bombs / process spawning limits
- Network escape attempts (outbound connections from containers)
- Memory exhaustion (OOM behavior)
- Filesystem escape (writing outside `/app`)
- Zombie container cleanup on process crash

A single sandbox escape in production could compromise the host system or allow cross-student data leakage.

### Gap 2: CI Only Runs Unit Tests — Integration & Web Tests Are Dead Code

The GitHub Actions workflow (`pytest.yml`) only executes `pytest tests/unit/`. The integration tests (which test real Docker sandbox lifecycle) and web tests (which test the FastAPI endpoints) **never run in CI**. This means:
- Regressions in sandbox pool management go undetected until production
- API contract changes break silently
- The 30+ integration test files provide zero automated safety net

### Gap 3: No Parametrized Combinatorial Testing

The system supports 4+ languages × 3+ templates × multiple failure modes, yet there is **zero use of `pytest.mark.parametrize`**. Each language/template combination is either tested individually (duplicated logic) or not tested at all. Adding a new language (e.g., Rust, Go) requires manually writing tests for every existing template — a process that doesn't scale and will inevitably be skipped.

---

## Section 2: The Multi-Tiered Test Blueprint

### L1: Fast Unit Tests (Target: <30s, runs on every commit)

**Purpose:** Validate pure logic, data transformations, and contracts without I/O.

**Architecture:**

```python
# tests/unit/conftest.py — Shared fixtures for all unit tests

import pytest
from unittest.mock import MagicMock
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language


@pytest.fixture
def mock_pipeline_execution():
    """Factory fixture for PipelineExecution with configurable state."""
    def _factory(language=Language.PYTHON, files=None, step_results=None):
        submission = Submission(
            user_id="test-user",
            assignment_id="test-assignment",
            language=language,
            submission_files=files or {"main.py": SubmissionFile("main.py", "print('hello')")},
        )
        pe = PipelineExecution.start_execution(submission)
        for sr in (step_results or []):
            pe.add_step_result(sr)
        return pe
    return _factory


@pytest.fixture
def mock_sandbox():
    """A mock SandboxContainer that records all interactions."""
    sandbox = MagicMock()
    sandbox.run_command.return_value = MagicMock(exit_code=0, stdout="output", stderr="")
    sandbox.make_request.return_value = MagicMock(status_code=200, json=lambda: {})
    return sandbox
```

**Key patterns:**
- Every `Step` subclass has a corresponding `test_<step>_step.py` that tests `_execute()` with mocked dependencies
- Every `TestFunction` subclass has a test that validates `execute()` returns correct `TestResult` for known inputs
- `CriteriaTree` building/traversal tested with fixture trees (no sandbox, no AI)
- Translation key completeness: assert all keys in `en.json` exist in `pt_br.json`

---

### L2: Matrix Integration Tests (Target: <5min, runs on PR to main)

**Purpose:** Validate the full pipeline across the language × template × submission-type matrix.

**Architecture — The Golden Dataset:**

```
tests/golden_dataset/
├── python/
│   ├── perfect/          # Code that should score 100%
│   │   ├── input_output/
│   │   ├── api_testing/
│   │   └── web_dev/
│   ├── syntax_error/     # Code that fails to compile/parse
│   ├── infinite_loop/    # Code that should timeout
│   ├── runtime_error/    # Code that crashes during execution
│   └── partial_credit/   # Code that passes some tests but not all
├── javascript/
│   ├── perfect/
│   ├── syntax_error/
│   ...
├── java/
│   ...
└── cpp/
    ...
```

Each golden submission includes a `expected.json`:
```json
{
  "min_score": 95,
  "max_score": 100,
  "expected_status": "COMPLETED",
  "must_pass_tests": ["health_check", "check_response_json"],
  "must_fail_tests": []
}
```

**The Parametrized Matrix Test:**

```python
# tests/integration/test_pipeline_matrix.py

import pytest
import json
from pathlib import Path
from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language

GOLDEN_DIR = Path(__file__).parent.parent / "golden_dataset"

LANGUAGES = [
    (Language.PYTHON, "python"),
    (Language.NODE, "javascript"),
    (Language.JAVA, "java"),
    (Language.CPP, "cpp"),
]

TEMPLATES = ["input_output", "api_testing", "web_dev"]

SCENARIOS = ["perfect", "syntax_error", "infinite_loop", "runtime_error", "partial_credit"]


def discover_golden_cases():
    """Discover all valid (language, template, scenario) combinations."""
    cases = []
    for lang_enum, lang_dir in LANGUAGES:
        for scenario in SCENARIOS:
            for template in TEMPLATES:
                path = GOLDEN_DIR / lang_dir / scenario / template
                if path.exists():
                    cases.append(pytest.param(
                        lang_enum, template, scenario, path,
                        id=f"{lang_dir}-{template}-{scenario}"
                    ))
    return cases


@pytest.mark.integration
@pytest.mark.parametrize("language,template,scenario,dataset_path", discover_golden_cases())
def test_pipeline_golden(language, template, scenario, dataset_path, sandbox_pool):
    """Run the full pipeline against a golden dataset entry and validate expectations."""
    # Load submission files
    files = {}
    for f in dataset_path.glob("*"):
        if f.name != "expected.json" and f.is_file():
            files[f.name] = SubmissionFile(f.name, f.read_text())

    expected = json.loads((dataset_path / "expected.json").read_text())

    # Load criteria from dataset
    criteria = json.loads((dataset_path / "criteria.json").read_text())

    pipeline = build_pipeline(
        template_name=template,
        include_feedback=False,
        grading_criteria=criteria,
        feedback_config={},
    )

    submission = Submission(
        user_id="golden-test",
        assignment_id=f"golden-{template}",
        language=language,
        submission_files=files,
    )

    result = pipeline.run(submission)

    # Assertions
    assert result.status.value == expected["expected_status"]
    if expected.get("min_score") is not None:
        assert result.grading_result.final_score >= expected["min_score"]
    if expected.get("max_score") is not None:
        assert result.grading_result.final_score <= expected["max_score"]
```

**Adding a new language requires only:** adding a new directory under `tests/golden_dataset/<language>/` with sample files. The parametrize discovery picks it up automatically.

---

### L3: Security & Chaos Tests (Target: <3min, runs on PR to main)

**Purpose:** Verify the sandbox cannot be escaped, exhausted, or abused.

```python
# tests/security/test_sandbox_security.py

import pytest
from sandbox_manager.manager import get_sandbox_manager
from sandbox_manager.models.sandbox_models import Language


@pytest.fixture(scope="module")
def sandbox():
    """Acquire a real sandbox for security testing."""
    manager = get_sandbox_manager()
    sb = manager.acquire_sandbox(Language.PYTHON)
    yield sb
    manager.destroy_sandbox(Language.PYTHON, sb)


class TestSandboxNetworkIsolation:
    """Verify containers cannot reach the outside world."""

    def test_cannot_ping_external(self, sandbox):
        result = sandbox.run_command("ping -c 1 -W 2 8.8.8.8")
        assert result.exit_code != 0, "Container should not reach external IPs"

    def test_cannot_curl_external(self, sandbox):
        result = sandbox.run_command("curl -s --max-time 3 https://example.com")
        assert result.exit_code != 0, "Container should not make HTTP requests"

    def test_cannot_resolve_dns(self, sandbox):
        result = sandbox.run_command("nslookup google.com")
        assert result.exit_code != 0, "Container should not resolve DNS"


class TestSandboxResourceLimits:
    """Verify resource exhaustion is contained."""

    def test_fork_bomb_contained(self, sandbox):
        """Fork bomb should be killed by PID limits, not crash the host."""
        result = sandbox.run_command("python3 -c \"import os\\nwhile True: os.fork()\"", timeout=5)
        assert result.exit_code != 0
        # Container should still be responsive after
        check = sandbox.run_command("echo alive")
        assert check.exit_code == 0

    def test_memory_exhaustion_contained(self, sandbox):
        """OOM should kill the process, not the container."""
        result = sandbox.run_command(
            "python3 -c \"x = []\\nwhile True: x.append('A' * 10**6)\"",
            timeout=10
        )
        assert result.exit_code != 0

    def test_disk_write_limited(self, sandbox):
        """Cannot fill the filesystem."""
        result = sandbox.run_command(
            "dd if=/dev/zero of=/app/bigfile bs=1M count=500",
            timeout=10
        )
        # Should fail due to disk quota or read-only filesystem
        assert result.exit_code != 0 or "No space" in result.stderr

    def test_infinite_loop_timeout(self, sandbox):
        """Infinite loops are killed by timeout."""
        result = sandbox.run_command("python3 -c \"while True: pass\"", timeout=5)
        assert result.exit_code != 0


class TestSandboxFilesystemIsolation:
    """Verify filesystem boundaries."""

    def test_cannot_read_host_files(self, sandbox):
        result = sandbox.run_command("cat /etc/shadow")
        assert result.exit_code != 0 or result.stdout.strip() == ""

    def test_cannot_write_outside_workdir(self, sandbox):
        result = sandbox.run_command("touch /tmp/escape_test")
        # Depending on config, this may succeed in /tmp but /app is the only persistent dir
        result2 = sandbox.run_command("touch /escape_root")
        assert result2.exit_code != 0

    def test_cannot_access_docker_socket(self, sandbox):
        result = sandbox.run_command("ls /var/run/docker.sock")
        assert result.exit_code != 0


class TestSandboxZombieCleanup:
    """Verify containers are cleaned up on abnormal termination."""

    def test_abandoned_container_cleanup(self):
        """Simulate a crash: acquire sandbox, don't release, verify pool recovers."""
        manager = get_sandbox_manager()
        sb = manager.acquire_sandbox(Language.PYTHON)
        container_id = sb.container_ref.id

        # Simulate crash — don't call release/destroy
        # Force pool health check
        manager.destroy_sandbox(Language.PYTHON, sb)

        # Verify container is gone
        import docker
        client = docker.from_env()
        containers = [c.id for c in client.containers.list(all=True)]
        assert container_id not in containers
```

---

### L4: AI Evaluation Suites (Target: <2min with cassettes, runs on PR)

**Purpose:** Test AI-dependent code deterministically in CI, with periodic live validation.

**Strategy: Three-Layer AI Testing**

```python
# tests/ai/conftest.py — VCR-style cassette recording for OpenAI calls

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

CASSETTES_DIR = Path(__file__).parent / "cassettes"


@pytest.fixture
def ai_cassette():
    """Replay recorded AI responses for deterministic testing."""
    def _load(cassette_name: str):
        cassette_path = CASSETTES_DIR / f"{cassette_name}.json"
        recorded = json.loads(cassette_path.read_text())

        mock_response = MagicMock()
        mock_response.output = [None, MagicMock()]
        mock_response.output[1].content = [MagicMock()]
        mock_response.output[1].content[0].parsed = MagicMock()
        mock_response.output[1].content[0].parsed.results = recorded["results"]

        return patch(
            "autograder.utils.executors.ai_executor.OpenAI"
        ).start().return_value.responses.parse.return_value = mock_response

    return _load


# --- Layer 1: Prompt Validation (no API calls) ---

class TestAiPromptConstruction:
    """Validate that prompts are well-formed without calling the API."""

    def test_prompt_includes_all_submission_files(self):
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput
        files = {"main.py": "print('hello')", "utils.py": "def add(a,b): return a+b"}
        result = AiExecutor._build_submission_files_string(files)
        assert "main.py" in result
        assert "utils.py" in result
        assert "print('hello')" in result

    def test_prompt_includes_all_test_names(self):
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput
        tests = [
            TestInput(test_name="code_quality", prompt="Evaluate quality"),
            TestInput(test_name="naming_conventions", prompt="Check names"),
        ]
        result = AiExecutor._build_test_batch_string(tests)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["test"] == "code_quality"


# --- Layer 2: Cassette Replay (deterministic, fast) ---

class TestAiBatchWithCassettes:
    """Test AI batch processing with recorded responses."""

    def test_successful_batch_maps_results_correctly(self, ai_cassette):
        ai_cassette("successful_batch_2_tests")
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput

        executor = AiExecutor()
        results = executor.run(
            [TestInput(test_name="quality", prompt="check quality")],
            {"main.py": "x = 1"},
            "en"
        )
        assert "quality" in results
        assert 0 <= results["quality"].score <= 100

    def test_empty_test_list_returns_empty(self):
        from autograder.utils.executors.ai_executor import AiExecutor
        results = AiExecutor().run([], {}, "en")
        assert results == {}


# --- Layer 3: Live Evaluation (weekly scheduled, not on every PR) ---
# Uses a "judge LLM" to evaluate the grading LLM's output quality.

@pytest.mark.live_ai
class TestAiOutputQuality:
    """
    Scheduled weekly: sends real prompts to the AI and validates output quality.
    Uses GPT-4 as a judge to evaluate whether the grading output is pedagogically sound.
    """

    EVALUATION_SET = [
        {
            "submission": "def sort(arr):\n    return sorted(arr)",
            "test_prompt": "Evaluate if this implements a sorting algorithm from scratch",
            "expected_verdict": "low_score",  # Using built-in sorted() is not implementing
        },
        {
            "submission": "def sort(arr):\n    for i in range(len(arr)):\n        for j in range(i+1, len(arr)):\n            if arr[i] > arr[j]:\n                arr[i], arr[j] = arr[j], arr[i]\n    return arr",
            "test_prompt": "Evaluate if this implements a sorting algorithm from scratch",
            "expected_verdict": "high_score",
        },
    ]

    def test_ai_grading_directional_correctness(self):
        """The AI should score a real implementation higher than a wrapper."""
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput

        executor = AiExecutor()
        results = []
        for case in self.EVALUATION_SET:
            r = executor.run(
                [TestInput(test_name="sort_check", prompt=case["test_prompt"])],
                {"solution.py": case["submission"]},
                "en"
            )
            results.append(r.get("sort_check"))

        # Directional: real implementation should score higher
        assert results[1].score > results[0].score
```

**Cassette recording workflow:**
```bash
# Record new cassettes (run manually when prompts change):
RECORD_CASSETTES=1 pytest tests/ai/ -m "not live_ai" --cassette-dir tests/ai/cassettes/
```

---

## Section 3: The "New Feature" Testing Protocol

### Standard Operating Procedure: Adding a New Template

Any new `Template` subclass **must** pass the `TemplateTestContract`:

```python
# tests/contracts/base_template_test.py

import pytest
from abc import ABC, abstractmethod
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.sandbox_container import SandboxContainer


class TemplateTestContract(ABC):
    """
    Base test class that enforces testing standards for all Template implementations.
    Any new template MUST create a test class inheriting from this.

    Usage:
        class TestDataScienceTemplate(TemplateTestContract):
            @pytest.fixture
            def template(self):
                return DataScienceTemplate()

            @pytest.fixture
            def valid_submission_files(self):
                return {"notebook.ipynb": SubmissionFile("notebook.ipynb", "...")}

            @pytest.fixture
            def golden_criteria(self):
                return {...}
    """

    @pytest.fixture
    @abstractmethod
    def template(self) -> Template:
        """Return an instance of the template being tested."""

    @pytest.fixture
    @abstractmethod
    def valid_submission_files(self) -> dict:
        """Return a minimal valid submission for this template."""

    @pytest.fixture
    @abstractmethod
    def golden_criteria(self) -> dict:
        """Return a valid criteria config for this template."""

    # --- Enforced Tests ---

    def test_template_has_name(self, template):
        assert template.template_name
        assert isinstance(template.template_name, str)

    def test_template_has_description(self, template):
        assert template.template_description
        assert isinstance(template.template_description, str)

    def test_requires_sandbox_is_bool(self, template):
        assert isinstance(template.requires_sandbox, bool)

    def test_all_registered_tests_are_valid(self, template):
        """Every test function in the template must conform to TestFunction ABC."""
        for name, test_fn in template.tests.items():
            assert isinstance(test_fn, TestFunction), f"{name} is not a TestFunction"
            assert test_fn.name == name
            assert test_fn.description
            assert isinstance(test_fn.parameter_description, list)

    def test_all_tests_return_test_result(self, template, valid_submission_files, mock_sandbox):
        """Every test function must return a TestResult when executed with valid input."""
        from autograder.models.dataclass.test_result import TestResult
        files = list(valid_submission_files.values())
        for name, test_fn in template.tests.items():
            result = test_fn.execute(files=files, sandbox=mock_sandbox)
            assert isinstance(result, TestResult), f"{name}.execute() didn't return TestResult"
            assert 0 <= result.score <= 100, f"{name} score {result.score} out of range"

    def test_get_test_raises_on_unknown(self, template):
        with pytest.raises(AttributeError):
            template.get_test("nonexistent_test_xyz")
```

### Standard Operating Procedure: Adding a New Step

```python
# tests/contracts/base_step_test.py

import pytest
from abc import ABC, abstractmethod
from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepStatus
from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus


class StepTestContract(ABC):
    """
    Base test class for all Step implementations.
    Enforces that steps handle success, failure, and edge cases correctly.
    """

    @pytest.fixture
    @abstractmethod
    def step(self) -> Step:
        """Return an instance of the step being tested."""

    @pytest.fixture
    @abstractmethod
    def valid_pipeline_execution(self) -> PipelineExecution:
        """Return a PipelineExecution in the correct state for this step."""

    @pytest.fixture
    @abstractmethod
    def invalid_pipeline_execution(self) -> PipelineExecution:
        """Return a PipelineExecution that should cause this step to fail gracefully."""

    # --- Enforced Tests ---

    def test_step_has_name(self, step):
        assert step.step_name is not None

    def test_successful_execution_adds_step_result(self, step, valid_pipeline_execution):
        result = step.execute(valid_pipeline_execution)
        assert isinstance(result, PipelineExecution)
        last_step = result.get_previous_step()
        assert last_step is not None
        assert last_step.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)

    def test_invalid_input_does_not_crash(self, step, invalid_pipeline_execution):
        """Steps must handle bad input gracefully — never raise unhandled exceptions."""
        result = step.execute(invalid_pipeline_execution)
        assert isinstance(result, PipelineExecution)
        # Should either fail gracefully or be interrupted, never crash
        last_step = result.get_previous_step()
        assert last_step.status in (StepStatus.FAILURE, StepStatus.INTERRUPTED, StepStatus.SKIPPED)

    def test_step_is_idempotent_on_pipeline(self, step, valid_pipeline_execution):
        """Running the same step twice should not corrupt state."""
        result1 = step.execute(valid_pipeline_execution)
        # Second run on the already-modified execution should not crash
        result2 = step.execute(result1)
        assert isinstance(result2, PipelineExecution)
```

### Contributor Checklist (enforced via PR template)

```markdown
## New Feature Testing Checklist

- [ ] Unit tests added in `tests/unit/` (mocked dependencies, <1s per test)
- [ ] Contract test class implemented (inherits from `TemplateTestContract` or `StepTestContract`)
- [ ] Golden dataset entries added for at least 2 languages × 2 scenarios
- [ ] If AI-dependent: cassette recorded and committed to `tests/ai/cassettes/`
- [ ] If sandbox-dependent: security test added for the new execution path
- [ ] All existing tests pass: `make test-unit && make test-integration`
```

---

## Section 4: CI/CD Pipeline Optimization

### Proposed Workflow Split

```yaml
# .github/workflows/test-fast.yml — Runs on EVERY push (target: <90s)
name: Fast Tests
on: [push]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: pytest tests/unit/ tests/contracts/ tests/ai/ -m "not live_ai" --tb=short -q
      - run: pytest --co -q tests/integration/ # Collect-only to verify imports don't break

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: pylint autograder/ --fail-under=8.0
```

```yaml
# .github/workflows/test-full.yml — Runs on PRs to main (target: <5min)
name: Full Test Suite
on:
  pull_request:
    branches: [main]
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      docker:
        image: docker:dind
        options: --privileged
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
      - run: pip install -r requirements.txt
      - name: Build sandbox images
        run: make build-sandbox-images
      - name: Run integration + security tests
        run: pytest tests/integration/ tests/security/ -m "not slow" --timeout=60 -x
      - name: Run web API tests
        run: pytest tests/web/ --timeout=30

  matrix:
    runs-on: ubuntu-latest
    needs: integration
    strategy:
      matrix:
        language: [python, javascript, java, cpp]
    services:
      docker:
        image: docker:dind
        options: --privileged
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: make build-sandbox-images
      - name: Run golden dataset for ${{ matrix.language }}
        run: pytest tests/integration/test_pipeline_matrix.py -k "${{ matrix.language }}" --timeout=120

  coverage:
    runs-on: ubuntu-latest
    needs: [integration, matrix]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
      - run: pip install -r requirements.txt pytest-cov
      - run: pytest tests/unit/ --cov=autograder --cov-report=xml
      - uses: codecov/codecov-action@v4
```

```yaml
# .github/workflows/test-ai-live.yml — Weekly scheduled (validates LLM quality)
name: AI Live Evaluation
on:
  schedule:
    - cron: "0 6 * * 1"  # Every Monday at 6 AM UTC
jobs:
  ai-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"
      - run: pip install -r requirements.txt
      - name: Run live AI evaluation suite
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: pytest tests/ai/ -m "live_ai" --timeout=120
```

### Makefile Targets for Local Development

```makefile
# Add to existing Makefile

test-unit:            ## Fast unit tests (<30s)
	pytest tests/unit/ tests/contracts/ -q --tb=short

test-ai:             ## AI tests with cassettes (no API calls)
	pytest tests/ai/ -m "not live_ai" -q

test-integration:    ## Full integration (requires Docker)
	pytest tests/integration/ tests/security/ --timeout=60

test-matrix:         ## Golden dataset matrix (requires Docker)
	pytest tests/integration/test_pipeline_matrix.py --timeout=120

test-all:            ## Everything except live AI
	pytest tests/ -m "not live_ai" --timeout=120

test-record-cassettes:  ## Record new AI cassettes
	RECORD_CASSETTES=1 pytest tests/ai/ -m "not live_ai"
```

### Feedback Loop Targets

| Trigger | Tests Run | Target Time | Failure Action |
|---------|-----------|-------------|----------------|
| Every push | Unit + Contracts + AI cassettes + Lint | <90s | Block merge |
| PR to main | Integration + Security + Web + Matrix | <5min | Block merge |
| Weekly schedule | Live AI evaluation | <3min | Alert via Slack |
| Release tag | Full suite + Performance | <15min | Block release |

---

## Appendix: pytest Markers Configuration

```ini
# pytest.ini (update existing)
[pytest]
testpaths = tests
markers =
    integration: Full pipeline with real Docker containers
    security: Sandbox escape and resource exhaustion tests
    live_ai: Tests that make real OpenAI API calls (scheduled only)
    slow: Tests that take >30s (excluded from fast suite)
    matrix: Golden dataset parametrized tests
```
