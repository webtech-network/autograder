import logging

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from sandbox_manager.sandbox_container import SandboxContainer


# ===============================================================
# region: TestFunction for Input/Output Validation
# ===============================================================

class ExpectOutputTest(TestFunction):
    """
    Tests a command-line program by providing a series of inputs via stdin
    and comparing the program's stdout with an expected output.
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
            ParamDescription("program_command", "(Opcional) Comando para executar o programa (ex: 'python3 calc.py').", "string")
        ]

    def execute(self, files, sandbox: SandboxContainer, inputs: list = None, expected_output: str = "", program_command: str = None, **kwargs) -> TestResult:
        """
        Constructs and runs the command using stdin input for robust input handling,
        then validates the output.

        Args:
            files: Submission files (not used in this test)
            sandbox: The sandbox container to execute in
            inputs: List of input strings to send to the program
            expected_output: The expected output from the program
            program_command: Command to run the program (e.g., "python3 calculator.py")
        """
        # TODO: Implement more robust input handling and I/O validation

        try:
            if not program_command:
                # No program command specified - treat inputs as command to run
                # Join inputs into a single command string
                if inputs is None:
                    raise ValueError("inputs parameter is required")
                command = ' '.join(inputs) if isinstance(inputs, list) else str(inputs)
                output = sandbox.run_command(command)
                actual_output = output.stdout
            else:
                # Program command specified - inputs are stdin for the program
                output = sandbox.run_commands(inputs, program_command=program_command)
                actual_output = output.stdout

            score = 100.0 if actual_output.strip() == expected_output.strip() else 0.0
            report = f"Expected output: '{expected_output.strip()}'\nActual output: '{actual_output.strip()}'\n"

            # Include stderr if there was any error output
            if output.stderr:
                report += f"Error output (stderr): {output.stderr}\n"

            return TestResult(
                test_name=self.name,
                score=score,
                report=report
            )
        except Exception as e:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=f"Error executing command: {str(e)}"
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


