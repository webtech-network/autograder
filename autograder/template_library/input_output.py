import logging

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.services.command_resolver import CommandResolver
from sandbox_manager.sandbox_container import SandboxContainer


# ===============================================================
# Base TestFunction for Executable Validations
# ===============================================================

class BaseExecutionTest(TestFunction):
    """
    Abstract base class for tests that involve running a student's code
    in a sandbox and handling basic execution results (timeouts, crashes).
    """

    def __init__(self):
        self.command_resolver = CommandResolver()

    def run_sandbox_execution(self, sandbox: SandboxContainer, inputs: list = None,
                              program_command=None, __submission_language__=None, **kwargs):
        """
        Resolves the command and executes it inside the sandbox.
        Returns the raw `output` from the sandbox run.
        Can raise exceptions which the caller or subclass execute wrapper should catch.
        """
        # 1. Resolve the actual command
        resolved_command = None
        if program_command and __submission_language__:
            resolved_command = self.command_resolver.resolve_command(
                program_command,
                __submission_language__
            )

        # 2. Run the command
        if not resolved_command:
            if inputs is None: 
                raise ValueError("inputs parameter is required if no resolved command via language is found")
            command = ' '.join(inputs) if isinstance(inputs, list) else str(inputs)
            return sandbox.run_command(command)
        else:
            safe_inputs = inputs if inputs is not None else []
            return sandbox.run_commands(safe_inputs, program_command=resolved_command)

    def check_for_base_errors(self, output) -> TestResult:
        """
        Checks for Timeout, Compilation Error, or Runtime Error in the sandbox output.
        Returns a TestResult with score 0.0 if an error is found, or None if successful.
        """
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
            
        return None

# ===============================================================
# TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(BaseExecutionTest):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output.

    Supports multi-language submissions through dynamic command resolution.
    """

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
            output = self.run_sandbox_execution(
                sandbox=sandbox, 
                inputs=inputs, 
                program_command=program_command, 
                __submission_language__=__submission_language__, 
                **kwargs
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output)
            if error_result:
                return error_result

            # Standard I/O Comparison if execution succeeded
            actual_output = output.stdout.strip()
            expected = expected_output.strip()

            if actual_output == expected:
                return TestResult(
                    test_name=self.name,
                    score=100.0,
                    report="Success: Output matches expected values."
                )
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

class DontFailTest(BaseExecutionTest):
    """
    Tests that a command-line program does NOT crash when given a specific input.

    Unlike ExpectOutputTest, this test ignores the program's stdout entirely.
    It only checks that execution completes without a runtime error, compilation
    error, or timeout. Useful for validating error handling (e.g., sending a
    string when the program expects a number).
    """

    @property
    def name(self):
        return "dont_fail"

    @property
    def description(self):
        return "Executa o programa do aluno com uma entrada específica e verifica que ele não falha (sem crash, sem timeout)."

    @property
    def required_file(self):
        return None

    @property
    def parameter_description(self):
        return [
            ParamDescription("input", "String a ser enviada para o programa via stdin.", "string"),
            ParamDescription("program_command", "(Opcional) Comando para executar o programa. Pode ser uma string (legado), dict (multi-idioma), ou 'CMD' (auto-resolve).", "string or dict")
        ]

    def execute(self, files, sandbox: SandboxContainer, input: str = "",
                program_command=None, __submission_language__=None, **kwargs) -> TestResult:
        try:
            # Reformat scalar input to standard list
            inputs = [input] if input else []
            
            output = self.run_sandbox_execution(
                sandbox=sandbox, 
                inputs=inputs, 
                program_command=program_command, 
                __submission_language__=__submission_language__, 
                **kwargs
            )

            # Check for generic execution failures
            error_result = self.check_for_base_errors(output)
            if error_result:
                return error_result

            # Program completed without crashing — success!
            return TestResult(
                test_name=self.name,
                score=100.0,
                report="Success: Program executed without errors."
            )

        except Exception as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=f"SYSTEM ERROR: Internal autograder failure: {str(e)}"
            )



class InputOutputTemplate(Template):
    """
    A template for command-line I/O assignments. It uses the SandboxExecutor
    to securely run student programs and validate their console output.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.tests = {
            "expect_output": ExpectOutputTest(),
            "dont_fail": DontFailTest(),
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


