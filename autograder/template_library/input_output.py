import logging

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.services.command_resolver import CommandResolver
from sandbox_manager.sandbox_container import SandboxContainer


# ===============================================================
# region: TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(TestFunction):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output.

    Supports multi-language submissions through dynamic command resolution.
    """

    def __init__(self):
        self.command_resolver = CommandResolver()

    @property
    def name(self):
        return "expect_output"

    @property
    def description(self):
        return "Executa o programa do aluno, fornece uma série de entradas separadas por linha e verifica se a saída final está correta."

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("inputs", "Lista de strings a serem enviadas para o programa, cada uma em uma nova linha.", "list of strings"),
            ParamDescription("expected_output", "A única string que o programa deve imprimir na saída padrão.", "string"),
            ParamDescription("program_command", "(Opcional) Comando para executar o programa. Pode ser uma string (legado), dict (multi-idioma), ou 'CMD' (auto-resolve).", "string or dict")
        ]

    def execute(self, files, sandbox: SandboxContainer, inputs: list = None, expected_output: str = "",
                program_command=None, __submission_language__=None, **kwargs) -> TestResult:
        try:
            # 1. Resolve the actual command
            resolved_command = None
            if program_command and __submission_language__:
                resolved_command = self.command_resolver.resolve_command(
                    program_command,
                    __submission_language__
                )
            # ... (keep existing resolution logic) ...

            # 2. Run the command and get classified output
            if not resolved_command:
                if inputs is None: raise ValueError("inputs parameter is required")
                command = ' '.join(inputs) if isinstance(inputs, list) else str(inputs)
                output = sandbox.run_command(command)
            else:
                output = sandbox.run_commands(inputs, program_command=resolved_command)

            # 3. Handle specific execution failures based on Category
            # (Assuming you updated CommandResponse to include .category as suggested previously)
            from sandbox_manager.models.sandbox_models import ResponseCategory

            if output.category == ResponseCategory.TIMEOUT:
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=f"FAILURE: Program timed out. Ensure you don't have infinite loops. [Time: {output.execution_time:.2f}s]"
                )

            if output.category == ResponseCategory.COMPILATION_ERROR:
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=f"FAILURE: Compilation Error.\nDetails:\n{output.stderr}"
                )

            if output.category == ResponseCategory.RUNTIME_ERROR:
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=f"FAILURE: Your program crashed during execution.\nError:\n{output.stderr}"
                )

            # 4. Standard I/O Comparison if execution succeeded
            actual_output = output.stdout.strip()
            expected = expected_output.strip()

            if actual_output == expected:
                return TestResult(
                    test_name=self.name,
                    score=100.0,
                    report="Success: Output matches expected values."
                )
            else:
                return TestResult(
                    test_name=self.name,
                    score=0.0,
                    report=f"FAILURE: Output Mismatch.\nExpected: '{expected}'\nActual: '{actual_output}'"
                )

        except Exception as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=f"SYSTEM ERROR: Internal autograder failure: {str(e)}"
            )

# ===============================================================
# endregion
# ===============================================================

class InputOutputTemplate(Template):
    """
    A template for command-line I/O assignments. It uses the SandboxExecutor
    to securely run student programs and validate their console output.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "expect_output": ExpectOutputTest(),
        }

    @property
    def template_name(self):
        return "Input/Output"

    @property
    def template_description(self):
        return "Um modelo para avaliar trabalhos com base na entrada e saída de linha de comando."

    @property
    def requires_sandbox(self) -> bool:
        return True

    def get_test(self, name: str) -> TestFunction:
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function


